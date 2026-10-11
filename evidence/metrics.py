"""Evidence engine: aggregation, metrics, and cost radar.

MOCK runs, UNPRICED runs, and runs before the Stage 1e cutoff (2026-10-11 04:35:00 UTC)
are strictly excluded from metrics calculations.
"""
import json
import statistics
from pathlib import Path

import config
from agent.llm import PRICES
from experiments.ideas import HELD_OUT, TUNING

STAGE_1E_CUTOFF_UTC = "20261011-043500"

SOURCES = {
    "n_runs": "MEASURED",
    "success_count": "MEASURED",
    "success_rate": "MEASURED",
    "first_attempt_pass_count": "MEASURED",
    "first_attempt_pass_rate": "MEASURED",
    "avg_attempts": "MEASURED",
    "avg_tokens": "MEASURED",
    "median_latency_s": "MEASURED",
    "total_cost": "COMPUTED",
    "avg_cost": "COMPUTED",
    "cost_per_success": "COMPUTED",
    "retry_tax": "COMPUTED",
    "cost_by_stage": "COMPUTED",
    "tokens_per_success": "MEASURED",
    "model": "CONFIG",
    "temperature": "CONFIG",
    "pricing_date": "CONFIG",
}


def classify_idea(idea: str | None) -> str:
    """Map idea text to its experimental cohort ('tuning', 'held_out', or 'other')."""
    if not idea:
        return "other"
    cleaned = idea.strip()
    if cleaned in TUNING:
        return "tuning"
    if cleaned in HELD_OUT:
        return "held_out"
    return "other"


def is_pre_stage_1e(run_id: str, cutoff: str = STAGE_1E_CUTOFF_UTC) -> bool:
    """Return True if run was created before cutoff (YYYYMMDD-HHMMSS)."""
    ts_part = run_id.replace("-", "")[:14] if run_id else ""
    cutoff_ts = cutoff.replace("-", "")[:14]
    return ts_part < cutoff_ts


def load_runs(runs_dir=None, include_mock: bool = False,
              cutoff: str | None = STAGE_1E_CUTOFF_UTC) -> tuple[list[dict], dict]:
    """Load runs from disk, filtering out mocks, unpriced runs, and pre-1e runs.

    Returns:
        (valid_records, exclusions_summary)
    """
    valid: list[dict] = []
    exclusions = {
        "total_scanned": 0,
        "total_excluded": 0,
        "by_reason": {
            "pre_stage_1e": 0,
            "mock": 0,
            "unpriced": 0,
            "corrupt": 0,
        },
        "excluded_runs": [],
    }

    base = Path(runs_dir or config.RUNS)
    for p in sorted(base.glob("*/result.json")):
        exclusions["total_scanned"] += 1
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            exclusions["total_excluded"] += 1
            exclusions["by_reason"]["corrupt"] += 1
            exclusions["excluded_runs"].append({"run_id": p.parent.name, "reason": f"corrupt: {e}"})
            continue

        run_id = r.get("run_id", p.parent.name)

        # 1. Check cutoff date (Stage 1e hardening cutoff)
        if cutoff and is_pre_stage_1e(run_id, cutoff):
            exclusions["total_excluded"] += 1
            exclusions["by_reason"]["pre_stage_1e"] += 1
            exclusions["excluded_runs"].append({"run_id": run_id, "reason": "pre_stage_1e"})
            continue

        # 2. Check mock runs
        is_mock = bool(r.get("mock") or r.get("cost_tag") == "MOCK" or r.get("model") == "mock-model")
        if is_mock and not include_mock:
            exclusions["total_excluded"] += 1
            exclusions["by_reason"]["mock"] += 1
            exclusions["excluded_runs"].append({"run_id": run_id, "reason": "mock"})
            continue

        # 3. Check unpriced runs
        is_unpriced = (
            r.get("cost_tag") == "UNPRICED"
            or r.get("cost_usd") == "UNPRICED"
            or not isinstance(r.get("cost_usd"), (int, float))
            or r.get("pricing_known_for_model") is False
        )
        if is_unpriced:
            exclusions["total_excluded"] += 1
            exclusions["by_reason"]["unpriced"] += 1
            exclusions["excluded_runs"].append({"run_id": run_id, "reason": "unpriced"})
            continue

        valid.append(r)

    return valid, exclusions


def aggregate(records: list[dict]) -> dict:
    """Aggregate a slice of runs. Never crashes or sums strings."""
    n = len(records)
    if n == 0:
        return {
            "n_runs": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "first_attempt_pass_count": 0,
            "first_attempt_pass_rate": 0.0,
            "avg_attempts": 0.0,
            "avg_tokens": 0.0,
            "total_cost": 0.0,
            "avg_cost": 0.0,
            "cost_per_success": None,
            "retry_tax": 0.0,
            "cost_by_stage": {},
            "tokens_per_success": None,
            "median_latency_s": 0.0,
            "sources": SOURCES,
            "run_ids": [],
        }

    ok = sum(1 for r in records if bool(r.get("success")))
    fa = sum(1 for r in records if bool(r.get("first_attempt_passed")))

    # Safely sum costs - never sum strings
    total_cost = 0.0
    for r in records:
        c = r.get("cost_usd")
        if isinstance(c, (int, float)):
            total_cost += float(c)

    # Cost by stage
    stages: dict[str, float] = {}
    for r in records:
        cbs = r.get("cost_by_stage")
        if isinstance(cbs, dict):
            for stage_name, val in cbs.items():
                if isinstance(val, (int, float)):
                    stages[stage_name] = stages.get(stage_name, 0.0) + float(val)

    # retry_tax: cost incurred after the first build attempt divided by total cost (incl. autopsy)
    after_first_build = stages.get("retry", 0.0) + stages.get("autopsy", 0.0)
    retry_tax = (after_first_build / total_cost) if total_cost > 0.0 else 0.0

    # Tokens and attempts safely summed
    total_tokens = sum(int(r.get("tokens", 0) or 0) for r in records)
    total_attempts = sum(int(r.get("attempts", 0) or 0) for r in records)
    success_tokens = sum(int(r.get("tokens", 0) or 0) for r in records if bool(r.get("success")))

    latencies = [float(r["latency_s"]) for r in records if isinstance(r.get("latency_s"), (int, float))]
    med_latency = statistics.median(latencies) if latencies else 0.0

    return {
        "n_runs": n,
        "success_count": ok,
        "success_rate": round(ok / n, 4),
        "first_attempt_pass_count": fa,
        "first_attempt_pass_rate": round(fa / n, 4),
        "avg_attempts": round(total_attempts / n, 2),
        "avg_tokens": round(total_tokens / n, 1),
        "total_cost": round(total_cost, 6),
        "avg_cost": round(total_cost / n, 6),
        "cost_per_success": round(total_cost / ok, 6) if ok > 0 else None,
        "retry_tax": round(retry_tax, 4),
        "cost_by_stage": {k: round(v, 6) for k, v in sorted(stages.items())},
        "tokens_per_success": round(success_tokens / ok, 1) if ok > 0 else None,
        "median_latency_s": round(med_latency, 3),
        "model": records[0].get("model") if records else None,
        "temperature": records[0].get("temperature") if records else None,
        "pricing_date": records[0].get("pricing_date", PRICES.get("pricing_date")) if records else None,
        "sources": SOURCES,
        "run_ids": [r.get("run_id") for r in records if r.get("run_id")],
    }


def compute_metrics(runs_dir=None, cutoff: str | None = STAGE_1E_CUTOFF_UTC) -> dict:
    """Full metrics computation grouped per mode and per idea-set."""
    valid, exclusions = load_runs(runs_dir=runs_dir, include_mock=False, cutoff=cutoff)

    # Group by mode
    by_mode: dict[str, list[dict]] = {}
    for r in valid:
        m = r.get("mode", "unknown")
        by_mode.setdefault(m, []).append(r)

    # Group by idea set
    by_idea_set: dict[str, list[dict]] = {}
    for r in valid:
        cohort = classify_idea(r.get("idea"))
        by_idea_set.setdefault(cohort, []).append(r)

    # Group by mode and idea set
    by_mode_and_idea_set: dict[str, dict[str, list[dict]]] = {}
    for r in valid:
        m = r.get("mode", "unknown")
        cohort = classify_idea(r.get("idea"))
        by_mode_and_idea_set.setdefault(m, {}).setdefault(cohort, []).append(r)

    return {
        "overall": aggregate(valid),
        "by_mode": {m: aggregate(recs) for m, recs in sorted(by_mode.items())},
        "by_idea_set": {cohort: aggregate(recs) for cohort, recs in sorted(by_idea_set.items())},
        "by_mode_and_idea_set": {
            m: {cohort: aggregate(recs) for cohort, recs in sorted(cohorts.items())}
            for m, cohorts in sorted(by_mode_and_idea_set.items())
        },
        "exclusions": exclusions,
        "sources": SOURCES,
    }
