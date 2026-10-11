"""A/B experiment: baseline vs improved on the tuning set AND a held-out set.

Compares:
- Baseline: unchanged BUILDER_SYSTEM_V1
- Improved: BUILDER_SYSTEM_V1 plus the frozen winning Candidate B patch from evidence/patches/winner.txt

Writes:
- evidence/metrics.json (machine-readable aggregate)
- evidence/cost_radar.md (human-readable Cost Radar summary)

Autopsy is disabled (autopsy=False) during the experiment.
Failed runs are never dropped. Sequential execution.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
from pathlib import Path
import random
import subprocess

import config
from agent import loop, prompts
from agent.llm import LLM, price_for, PRICES
from agent.mock_llm import MockLLM
from evidence import metrics
from experiments import arms
from experiments.ideas import HELD_OUT, TUNING


def get_git_commit_hash() -> str:
    """Return the current git commit hash via read-only git rev-parse HEAD."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except Exception:
        return "unknown"


def render_ab_readme(payload: dict) -> str:
    """Render evidence/ab/README.md with reproduce command, prompt provenance, and run IDs."""
    meta = payload.get("meta", {})
    cell_ids = payload.get("cell_run_ids", {})
    exp = payload.get("experiment", {})

    lines = [
        "# Pocket Startup: Stage 2c A/B Experiment Audit & Run Log",
        "",
        "> **Reproduce Command:**",
        f"> ```bash\n> {meta.get('reproduce_command', 'python -m experiments.ab --repeats 4 --seed 42 --sleep 1.0')}\n> ```",
        "",
        "> [!NOTE]",
        "> **Statistical Independence Caveat:** The statistical calculations (Wilson score 95% confidence intervals and Fisher's exact tests) treat runs as independent observations. However, each startup idea repeats 4 times and arms are paired by idea across the interleaved schedule. Consequently, reported p-values and confidence intervals are indicative rather than cluster-adjusted inferential tests.",
        "",
        "## 1. Provenance & Prompt Verification",
        "",
        f"- **Model:** `{meta.get('model', 'unknown')}` `[CONFIG]`",
        f"- **Temperature:** `{meta.get('temperature', 'unknown')}` `[CONFIG]`",
        f"- **Random Seed:** `{meta.get('seed', 42)}` `[CONFIG]`",
        f"- **Git Commit Hash:** `{meta.get('git_commit_hash', 'unknown')}` `[CONFIG]`",
        f"- **Schedule:** Interleaved arms `(baseline, improved, baseline, improved...)` with deterministic seed shuffle `[CONFIG]`",
        f"- **Repeats per Idea:** `{meta.get('repeats', 4)}` `[CONFIG]`",
        f"- **Autopsy Execution:** Disabled (`autopsy=False`) across all runs `[CONFIG]`",
        "",
        "### Exact Prompt SHA-256 Hashes",
        f"- **`BUILDER_SYSTEM_V1` SHA-256:** `{meta.get('builder_system_v1_sha256', 'unknown')}`",
        f"- **Improved System Prompt (`BUILDER_SYSTEM_V1` + `winner.txt`) SHA-256:** `{meta.get('builder_system_improved_sha256', 'unknown')}`",
        f"- **`RETRY_USER` SHA-256:** `{meta.get('retry_user_sha256', 'unknown')}`",
        f"- **`winner.txt` Patch SHA-256:** `{meta.get('builder_v2_patch_sha256', 'unknown')}`",
        "",
        "## 2. Cell Run ID Manifest",
        "",
    ]

    for cell_key, ids in sorted(cell_ids.items()):
        cell_title = cell_key.replace("/", " / ").upper()
        lines.append(f"### Cell: {cell_title} (N={len(ids)})")
        if ids:
            lines.append("```text")
            for rid in ids:
                lines.append(rid)
            lines.append("```")
        else:
            lines.append("_No runs recorded_")
        lines.append("")

    lines.extend([
        "## 3. Statistical Verification & Highlights",
        "",
        "- Complete tabular comparison, token breakdowns, Wilson 95% intervals, and Fisher exact test values are in [`cost_radar.md`](../cost_radar.md).",
        "- Machine-readable aggregate metrics are in [`metrics.json`](../metrics.json).",
        "",
    ])

    return "\n".join(lines)


async def run_ab_experiment(repeats: int = 4, seed: int = 42, llm=None, runs_dir=None,
                            metrics_path=None, cost_radar_path=None, readme_path=None,
                            progress_path=None, resume: bool = True, fresh: bool = False,
                            sleep_s: float = 1.0, emit=None) -> dict:
    """Execute the full A/B evaluation across tuning and held-out idea sets with interleaved arms.
    
    Supports seamless resume from progress checkpoint. Historical pilot runs on disk are strictly excluded.
    """
    llm = llm or LLM()
    target_metrics_path = Path(metrics_path or config.METRICS_PATH)
    target_cost_radar_path = Path(cost_radar_path or (config.EVIDENCE / "cost_radar.md"))
    target_readme_path = Path(readme_path or (config.EVIDENCE / "ab" / "README.md"))
    target_progress_path = Path(progress_path or (config.EVIDENCE / "ab" / "progress.json"))
    base_runs_dir = Path(runs_dir or config.RUNS)

    patch = loop.load_winner_patch()
    if patch is None:
        print("WARNING: evidence/patches/winner.txt not found; falling back to DEFAULT_V2_PATCH.")
        patch_used = prompts.DEFAULT_V2_PATCH
    else:
        patch_used = patch

    # Provenance prompt strings and SHA-256 hashes
    v1_text = prompts.BUILDER_SYSTEM_V1
    v1_sha256 = hashlib.sha256(v1_text.encode("utf-8")).hexdigest()
    improved_text = loop.builder_system("improved", patch_used)
    improved_sha256 = hashlib.sha256(improved_text.encode("utf-8")).hexdigest()
    retry_text = prompts.RETRY_USER
    retry_sha256 = hashlib.sha256(retry_text.encode("utf-8")).hexdigest()
    patch_sha256 = hashlib.sha256(patch_used.encode("utf-8")).hexdigest()
    git_hash = get_git_commit_hash()

    rng = random.Random(seed)

    experiment = {}
    all_recs = []
    arm_records = {"baseline": [], "improved": []}
    cell_records = {
        "tuning": {"baseline": [], "improved": []},
        "held_out": {"baseline": [], "improved": []},
    }

    # Resume check
    completed_slots = {}
    if resume and not fresh and target_progress_path.exists():
        try:
            p_data = json.loads(target_progress_path.read_text(encoding="utf-8"))
            p_meta = p_data.get("meta", {})
            if (p_meta.get("repeats") == repeats and
                p_meta.get("seed") == seed and
                p_meta.get("model") == llm.model and
                p_meta.get("builder_system_v1_sha256") == v1_sha256 and
                p_meta.get("builder_system_improved_sha256") == improved_sha256):
                completed_slots = p_data.get("completed_slots", {})
                print(f"[RESUME] Found existing checkpoint with {len(completed_slots)} completed runs: {target_progress_path}")
            else:
                print(f"[RESUME] Checkpoint parameters do not match current run configuration; starting fresh.")
        except Exception as e:
            print(f"[RESUME] Warning: could not parse checkpoint {target_progress_path} ({e}); starting fresh.")

    print("\n" + "=" * 70)
    print(" POCKET STARTUP: A/B EXPERIMENT & COST RADAR EVALUATION")
    print(f" Model: {llm.model} | Temp: {llm.temperature} | Repeats: {repeats} per arm per set")
    print(f" Schedule: Interleaved (baseline, improved, baseline, improved...) | Seed: {seed}")
    print(f" Git Commit Hash:          {git_hash}")
    print(f" Builder V1 SHA-256:       {v1_sha256[:16]}...")
    print(f" Builder Improved SHA-256: {improved_sha256[:16]}...")
    print(f" Retry User SHA-256:       {retry_sha256[:16]}...")
    print(f" Winner Patch SHA-256:     {patch_sha256[:16]}...")
    print("=" * 70)

    for set_name, ideas in (("tuning", TUNING), ("held_out", HELD_OUT)):
        experiment[set_name] = {}
        pairs = [(idea, rep, idx) for rep in range(1, repeats + 1) for idx, idea in enumerate(ideas, 1)]
        rng.shuffle(pairs)

        total_split_runs = len(pairs) * 2
        print(f"\n--- Running Split: {set_name.upper()} ({len(ideas)} ideas x {repeats} reps x 2 arms = {total_split_runs} runs) ---")

        run_idx_in_split = 0
        for idea, rep, idea_idx in pairs:
            # 1. Baseline arm
            run_idx_in_split += 1
            slot_b_key = f"{set_name}:baseline:rep{rep}:idea{idea_idx}"
            rec_b = None
            if slot_b_key in completed_slots:
                rid = completed_slots[slot_b_key]
                res_file = base_runs_dir / rid / "result.json"
                if res_file.exists():
                    try:
                        rec_b = json.loads(res_file.read_text(encoding="utf-8"))
                        print(f"  [{set_name.upper()} #{run_idx_in_split:02d}/{total_split_runs:02d} | Rep {rep}/{repeats} Idea {idea_idx}/{len(ideas)}] [SKIPPED/RESUMED: {rid}] {arms.describe(rec_b)}")
                    except Exception:
                        rec_b = None

            if rec_b is None:
                rec_b = await loop.run_build(
                    idea=idea,
                    mode="baseline",
                    llm=llm,
                    template="tip_splitter",
                    patch=None,
                    autopsy=False,
                    runs_dir=runs_dir,
                    emit=emit,
                )
                print(f"  [{set_name.upper()} #{run_idx_in_split:02d}/{total_split_runs:02d} | Rep {rep}/{repeats} Idea {idea_idx}/{len(ideas)}] {arms.describe(rec_b)}")
                completed_slots[slot_b_key] = rec_b["run_id"]
                # Save checkpoint atomically
                _save_progress(target_progress_path, repeats, seed, llm.model, v1_sha256, improved_sha256, completed_slots)
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            cell_records[set_name]["baseline"].append(rec_b)
            arm_records["baseline"].append(rec_b)
            all_recs.append(rec_b)

            # 2. Improved arm
            run_idx_in_split += 1
            slot_i_key = f"{set_name}:improved:rep{rep}:idea{idea_idx}"
            rec_i = None
            if slot_i_key in completed_slots:
                rid = completed_slots[slot_i_key]
                res_file = base_runs_dir / rid / "result.json"
                if res_file.exists():
                    try:
                        rec_i = json.loads(res_file.read_text(encoding="utf-8"))
                        print(f"  [{set_name.upper()} #{run_idx_in_split:02d}/{total_split_runs:02d} | Rep {rep}/{repeats} Idea {idea_idx}/{len(ideas)}] [SKIPPED/RESUMED: {rid}] {arms.describe(rec_i)}")
                    except Exception:
                        rec_i = None

            if rec_i is None:
                rec_i = await loop.run_build(
                    idea=idea,
                    mode="improved",
                    llm=llm,
                    template="tip_splitter",
                    patch=patch_used,
                    autopsy=False,
                    runs_dir=runs_dir,
                    emit=emit,
                )
                print(f"  [{set_name.upper()} #{run_idx_in_split:02d}/{total_split_runs:02d} | Rep {rep}/{repeats} Idea {idea_idx}/{len(ideas)}] {arms.describe(rec_i)}")
                completed_slots[slot_i_key] = rec_i["run_id"]
                # Save checkpoint atomically
                _save_progress(target_progress_path, repeats, seed, llm.model, v1_sha256, improved_sha256, completed_slots)
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            cell_records[set_name]["improved"].append(rec_i)
            arm_records["improved"].append(rec_i)
            all_recs.append(rec_i)

        # Aggregate per cell for this split
        experiment[set_name]["baseline"] = metrics.aggregate(cell_records[set_name]["baseline"])
        experiment[set_name]["improved"] = metrics.aggregate(cell_records[set_name]["improved"])

    # Combined totals across both cohorts per arm
    experiment["combined"] = {
        "baseline": metrics.aggregate(arm_records["baseline"]),
        "improved": metrics.aggregate(arm_records["improved"]),
    }

    # Fisher exact test for each cohort (baseline vs improved first-attempt pass rates)
    fisher_p_values = {}
    for cohort in ("tuning", "held_out", "combined"):
        b_cell = experiment[cohort]["baseline"]
        i_cell = experiment[cohort]["improved"]
        b_fa = b_cell.get("first_attempt_pass_count", 0)
        b_n = b_cell.get("n_runs", 0)
        b_fail = max(0, b_n - b_fa)
        i_fa = i_cell.get("first_attempt_pass_count", 0)
        i_n = i_cell.get("n_runs", 0)
        i_fail = max(0, i_n - i_fa)
        p_val = metrics.fisher_exact_2x2(b_fa, b_fail, i_fa, i_fail)
        fisher_p_values[cohort] = {
            "p_value": p_val,
            "tag": "COMPUTED",
            "n_baseline": b_n,
            "n_improved": i_n,
            "first_passes_baseline": b_fa,
            "first_passes_improved": i_fa,
        }
        experiment[cohort]["fisher_exact_p_value"] = p_val

    is_mock = bool(llm.mock or llm.model == "mock-model")
    pricing_source = "MOCK" if is_mock else PRICES.get("source", "COMPUTED")

    reproduce_cmd = f"python -m experiments.ab --repeats {repeats} --seed {seed} --sleep {sleep_s}"

    output_payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "experiment": experiment,
        "meta": {
            "model": llm.model,
            "temperature": llm.temperature,
            "git_commit_hash": git_hash,
            "pricing_date": PRICES.get("pricing_date"),
            "pricing_source": pricing_source,
            "repeats": repeats,
            "seed": seed,
            "interleaved": True,
            "autopsy_enabled": False,
            "ideas_per_set": len(TUNING),
            "builder_system_v1_sha256": v1_sha256,
            "builder_system_improved_sha256": improved_sha256,
            "builder_system_improved_text": improved_text,
            "retry_user_sha256": retry_sha256,
            "builder_v2_patch": patch_used,
            "builder_v2_patch_sha256": patch_sha256,
            "reproduce_command": reproduce_cmd,
            "note": "Counts are reported next to rates. N is small; read the counts, not just the percentages.",
        },
        "cell_run_ids": {
            f"{s}/{m}": [r.get("run_id") for r in cell_records[s][m] if r.get("run_id")]
            for s in ("tuning", "held_out")
            for m in ("baseline", "improved")
        },
        "fisher_exact_p_values": fisher_p_values,
        "neatlogs_trace_links": {
            "baseline_failure": "",
            "improved_success": "",
        },
        "run_ids": [r.get("run_id") for r in all_recs if r.get("run_id")],
        "sources": metrics.SOURCES,
    }

    # 1. Write machine-readable metrics.json
    target_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    target_metrics_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    print(f"\n[OK] Wrote machine-readable metrics: {target_metrics_path}")

    # 2. Render and write human-readable Cost Radar summary
    radar_md = metrics.render_cost_radar(output_payload)
    target_cost_radar_path.parent.mkdir(parents=True, exist_ok=True)
    target_cost_radar_path.write_text(radar_md, encoding="utf-8")
    print(f"[OK] Wrote human-readable Cost Radar: {target_cost_radar_path}")

    # 3. Write reproduce command and run IDs to evidence/ab/README.md
    target_readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_md = render_ab_readme(output_payload)
    target_readme_path.write_text(readme_md, encoding="utf-8")
    print(f"[OK] Wrote A/B audit and run ID manifest: {target_readme_path}")

    # 4. Mark progress checkpoint as completed
    _save_progress(target_progress_path, repeats, seed, llm.model, v1_sha256, improved_sha256, completed_slots, status="completed")

    # Print summary to terminal
    print("\n" + radar_md)
    print("=" * 70)

    return output_payload


def _save_progress(progress_path: Path, repeats: int, seed: int, model: str,
                   v1_sha: str, impr_sha: str, completed_slots: dict, status: str = "in_progress"):
    try:
        payload = {
            "meta": {
                "repeats": repeats,
                "seed": seed,
                "model": model,
                "status": status,
                "builder_system_v1_sha256": v1_sha,
                "builder_system_improved_sha256": impr_sha,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            "completed_slots": completed_slots,
        }
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[PROGRESS WARNING] Could not persist progress: {e}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run A/B experiment: baseline vs improved on tuning and held-out ideas.")
    parser.add_argument("--repeats", type=int, default=4, help="Repetitions per idea and arm (default: 4)")
    parser.add_argument("--seed", type=int, default=42, help="Fixed random seed for interleaving (default: 42)")
    parser.add_argument("--mock", action="store_true", help="Run with MockLLM instead of real Gemini client")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between runs (default: 1.0)")
    parser.add_argument("--fresh", action="store_true", help="Start fresh and ignore/overwrite existing progress checkpoint")
    parser.add_argument("--no-resume", action="store_true", help="Disable resuming from existing progress checkpoint")
    args = parser.parse_args(argv)

    llm = MockLLM() if args.mock else LLM()
    asyncio.run(run_ab_experiment(
        repeats=args.repeats,
        seed=args.seed,
        llm=llm,
        sleep_s=args.sleep,
        resume=not args.no_resume,
        fresh=args.fresh,
    ))


if __name__ == "__main__":
    main()
