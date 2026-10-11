"""Report command: aggregates post-1e baseline runs and prints summary metrics."""
import argparse
import sys
from pathlib import Path

from evidence import metrics


def format_currency(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"${val:.6f}"


def format_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def generate_report(runs_dir=None, cutoff=metrics.STAGE_1E_CUTOFF_UTC) -> str:
    data = metrics.compute_metrics(runs_dir=runs_dir, cutoff=cutoff)
    ex = data["exclusions"]
    baseline = data["by_mode"].get("baseline", metrics.aggregate([]))
    by_idea = data["by_idea_set"]

    lines = []
    lines.append("=" * 72)
    lines.append("  POCKET STARTUP: POST-STAGE 1e BASELINE RUNS REPORT")
    lines.append("=" * 72)
    lines.append(f"Cutoff UTC:            {cutoff[:8]} {cutoff[9:11]}:{cutoff[11:13]}:{cutoff[13:15]} UTC (runs before excluded)")
    lines.append(f"Total Runs Scanned:    {ex['total_scanned']} [MEASURED]")
    lines.append(f"Total Runs Excluded:   {ex['total_excluded']} [MEASURED]")
    for reason, count in ex["by_reason"].items():
        if count > 0:
            lines.append(f"  - Excluded ({reason}): {count}")
    lines.append(f"Valid Post-1e Runs:    {baseline['n_runs']} [MEASURED]")
    lines.append("-" * 72)
    lines.append("BASELINE OVERALL AGGREGATES:")
    lines.append(f"  Runs:                  {baseline['n_runs']} [MEASURED]")
    lines.append(f"  Success Count:         {baseline['success_count']} / {baseline['n_runs']} [MEASURED]")
    lines.append(f"  Success Rate:          {format_pct(baseline['success_rate'])} [MEASURED]")
    lines.append(f"  First-Attempt Passed:  {baseline['first_attempt_pass_count']} / {baseline['n_runs']} [MEASURED]")
    lines.append(f"  First-Attempt Rate:    {format_pct(baseline['first_attempt_pass_rate'])} [MEASURED]")
    lines.append(f"  Avg Attempts:          {baseline['avg_attempts']} [MEASURED]")
    lines.append(f"  Avg Tokens:            {baseline['avg_tokens']} [MEASURED]")
    lines.append(f"  Median Latency:        {baseline['median_latency_s']}s [MEASURED]")
    lines.append(f"  Total Cost:            {format_currency(baseline['total_cost'])} [COMPUTED]")
    lines.append(f"  Avg Cost per Run:      {format_currency(baseline['avg_cost'])} [COMPUTED]")
    lines.append(f"  Cost per Success:      {format_currency(baseline['cost_per_success'])} [COMPUTED]")
    lines.append(f"  Retry Tax:             {format_pct(baseline['retry_tax'])} [COMPUTED]")
    lines.append(f"                         (cost after 1st build / total cost, incl. autopsy)")

    lines.append("  Cost by Stage:         [COMPUTED]")
    for stage, cost in baseline["cost_by_stage"].items():
        pct = (cost / baseline["total_cost"] * 100) if baseline["total_cost"] else 0.0
        lines.append(f"    - {stage:<10}:        {format_currency(cost)} ({pct:.1f}%)")

    lines.append("-" * 72)
    lines.append("COHORT BREAKDOWN (Tuning vs. Held-Out):")
    for cohort in ("tuning", "held_out"):
        agg = by_idea.get(cohort, metrics.aggregate([]))
        lines.append(f"  [{cohort.upper()}] (n={agg['n_runs']}):")
        lines.append(f"    Success Rate:        {format_pct(agg['success_rate'])} [MEASURED]")
        lines.append(f"    First-Attempt Rate:  {format_pct(agg['first_attempt_pass_rate'])} [MEASURED]")
        lines.append(f"    Avg Attempts:        {agg['avg_attempts']} [MEASURED]")
        lines.append(f"    Avg Tokens:          {agg['avg_tokens']} [MEASURED]")
        lines.append(f"    Total Cost:          {format_currency(agg['total_cost'])} [COMPUTED]")
        lines.append(f"    Cost per Success:    {format_currency(agg['cost_per_success'])} [COMPUTED]")
        lines.append(f"    Retry Tax:           {format_pct(agg['retry_tax'])} [COMPUTED]")
        lines.append(f"    Median Latency:      {agg['median_latency_s']}s [MEASURED]")

    lines.append("-" * 72)
    lines.append("INCLUDED POST-1e BASELINE RUNS:")
    valid_recs, _ = metrics.load_runs(runs_dir=runs_dir, include_mock=False, cutoff=cutoff)
    baseline_recs = [r for r in valid_recs if r.get("mode") == "baseline"]
    for r in baseline_recs:
        rid = r.get("run_id")
        succ = "PASS" if r.get("success") else "FAIL"
        fa = "1st" if r.get("first_attempt_passed") else f"{r.get('attempts')} att"
        cost = format_currency(r.get("cost_usd"))
        idea = (r.get("idea") or "")[:42]
        lines.append(f"  {rid} | {succ:<4} | {fa:<7} | {cost} | {idea}")

    lines.append("=" * 72)
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report post-1e baseline metrics.")
    parser.add_argument("--runs-dir", default=None, help="Path to runs directory (default: config.RUNS)")
    args = parser.parse_args(argv)

    report_text = generate_report(runs_dir=args.runs_dir)
    print(report_text)


if __name__ == "__main__":
    main()
