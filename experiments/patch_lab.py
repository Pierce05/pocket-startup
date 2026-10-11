"""Patch Lab: Synthesize and test candidate prompt patches on the TUNING set.

Uses only tuning-set ideas and only post-1e autopsies as input.
Tests 2 candidate prompt patches (BUILDER_SYSTEM_V1 + candidate text) with 2 repeats each.
Selects winner by first-attempt pass count, tie-breaking on lower cost per success.
Writes evidence/patches/winner.txt and evidence/patches/results.json (retaining the loser).
"""
import argparse
import asyncio
import json
from pathlib import Path

import config
from agent import loop
from agent.llm import LLM
from agent.mock_llm import MockLLM
from evidence import metrics
from experiments.ideas import TUNING

# Synthesized from post-1e baseline autopsy clusters
CANDIDATE_A = (
    "Validate all inputs before computing. The bill and tip must be non-negative numbers, "
    "and the number of people must be a positive whole integer. If any input is empty, non-numeric, "
    "negative, or not a whole integer, display a clear message in #error and keep #result empty or hidden."
)

CANDIDATE_B = (
    "Before performing any calculation, check every numeric input. Verify that the bill is zero or greater, "
    "the tip percentage is zero or greater, and the number of people is a whole number greater than zero. "
    "On any invalid input, show an error message in #error and do not display anything in #result."
)

CANDIDATES = [
    {
        "id": "candidate_a",
        "name": "Candidate A (Type & Integer Constraint)",
        "patch": CANDIDATE_A,
    },
    {
        "id": "candidate_b",
        "name": "Candidate B (Pre-Calculation Checklist)",
        "patch": CANDIDATE_B,
    },
]


def collect_failed_baseline_autopsies(runs_dir=None, cutoff=metrics.STAGE_1E_CUTOFF_UTC) -> list[dict]:
    """Collect autopsies from post-1e baseline runs on the tuning set that failed attempt 1."""
    valid_recs, _ = metrics.load_runs(runs_dir=runs_dir, include_mock=False, cutoff=cutoff)
    autopsies = []
    base_dir = Path(runs_dir or config.RUNS)

    for r in valid_recs:
        if r.get("mode") == "baseline" and r.get("idea") in TUNING and not r.get("first_attempt_passed"):
            rid = r.get("run_id")
            p = base_dir / rid / "autopsy.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    autopsies.append({"run_id": rid, "idea": r.get("idea"), **data})
                except Exception:
                    pass
    return autopsies


def pick_winner(evaluated_candidates: list[dict]) -> tuple[dict, dict]:
    """Pick winner by first-attempt pass count, tie-break on lower cost per success."""
    def sort_key(cand):
        agg = cand["metrics"]
        fa_count = agg.get("first_attempt_pass_count", 0)
        cps = agg.get("cost_per_success")
        cost_key = float(cps) if (cps is not None and isinstance(cps, (int, float))) else float("inf")
        return (-fa_count, cost_key)

    sorted_cands = sorted(evaluated_candidates, key=sort_key)
    winner = sorted_cands[0]
    loser = sorted_cands[1] if len(sorted_cands) > 1 else sorted_cands[0]
    return winner, loser


async def run_patch_lab(repeats: int = 2, llm: LLM | None = None, runs_dir=None,
                        patch_dir=None, sleep_s: float = 1.0, emit=None) -> dict:
    """Execute the Patch Lab experiment over CANDIDATE_A and CANDIDATE_B."""
    llm = llm or LLM()
    target_patch_dir = Path(patch_dir or config.PATCH_DIR)
    target_patch_dir.mkdir(parents=True, exist_ok=True)

    evaluated = []

    for cand in CANDIDATES:
        cand_id = cand["id"]
        patch_text = cand["patch"]
        print(f"\n--- Testing {cand['name']} (mode={cand_id}, repeats={repeats}, {len(TUNING) * repeats} runs) ---")
        runs = []

        for rep in range(1, repeats + 1):
            for idx, idea in enumerate(TUNING, start=1):
                print(f"  [{cand_id}] Rep {rep}/{repeats} Idea {idx}/{len(TUNING)}: {idea[:45]}...")
                rec = await loop.run_build(
                    idea=idea,
                    mode=cand_id,
                    patch=patch_text,
                    template="tip_splitter",
                    autopsy=False,
                    llm=llm,
                    runs_dir=runs_dir,
                    emit=emit,
                )
                runs.append(rec)
                succ = "PASS" if rec.get("success") else "FAIL"
                fa = "1st-pass" if rec.get("first_attempt_passed") else f"att={rec.get('attempts')}"
                print(f"    -> {succ} ({fa}, cost=${rec.get('cost_usd')})")
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

        cand_metrics = metrics.aggregate(runs)
        evaluated.append({
            "candidate_id": cand_id,
            "name": cand["name"],
            "patch": patch_text,
            "metrics": cand_metrics,
            "run_ids": [r.get("run_id") for r in runs],
        })

    winner, loser = pick_winner(evaluated)

    results_data = {
        "winner": {
            "candidate_id": winner["candidate_id"],
            "name": winner["name"],
            "patch": winner["patch"],
            "first_attempt_pass_count": winner["metrics"]["first_attempt_pass_count"],
            "success_count": winner["metrics"]["success_count"],
            "n_runs": winner["metrics"]["n_runs"],
            "total_cost": winner["metrics"]["total_cost"],
            "cost_per_success": winner["metrics"]["cost_per_success"],
            "avg_attempts": winner["metrics"]["avg_attempts"],
            "metrics": winner["metrics"],
        },
        "loser": {
            "candidate_id": loser["candidate_id"],
            "name": loser["name"],
            "patch": loser["patch"],
            "first_attempt_pass_count": loser["metrics"]["first_attempt_pass_count"],
            "success_count": loser["metrics"]["success_count"],
            "n_runs": loser["metrics"]["n_runs"],
            "total_cost": loser["metrics"]["total_cost"],
            "cost_per_success": loser["metrics"]["cost_per_success"],
            "avg_attempts": loser["metrics"]["avg_attempts"],
            "metrics": loser["metrics"],
        },
        "candidates": evaluated,
    }

    # Write evidence/patches/winner.txt and evidence/patches/results.json
    winner_txt_path = target_patch_dir / "winner.txt"
    winner_txt_path.write_text(winner["patch"] + "\n", encoding="utf-8")

    results_json_path = target_patch_dir / "results.json"
    results_json_path.write_text(json.dumps(results_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"  PATCH LAB COMPLETE")
    print(f"  WINNER: {winner['name']} ({winner['candidate_id']})")
    print(f"    First-attempt passes: {winner['metrics']['first_attempt_pass_count']} / {winner['metrics']['n_runs']}")
    print(f"    Cost per success:     ${winner['metrics']['cost_per_success']}")
    print(f"    Avg attempts:         {winner['metrics']['avg_attempts']}")
    print(f"  Saved: {winner_txt_path}")
    print(f"  Saved: {results_json_path}")
    print("=" * 60)

    return results_data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Patch Lab candidate prompt competition on tuning set.")
    parser.add_argument("--repeats", type=int, default=2, help="Number of repeats per candidate across tuning set (default: 2)")
    parser.add_argument("--mock", action="store_true", help="Use MockLLM instead of real Gemini client")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between runs (default: 1.0)")
    args = parser.parse_args(argv)

    llm = MockLLM() if args.mock else LLM()
    asyncio.run(run_patch_lab(repeats=args.repeats, llm=llm, sleep_s=args.sleep))


if __name__ == "__main__":
    main()
