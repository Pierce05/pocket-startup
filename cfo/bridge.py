"""Render evidence/cfo/cfo_input.md from metrics.json, assumptions.yaml, and founder profile.

Every number carries an explicit tag: MEASURED, COMPUTED, USER-PROVIDED, ASSUMED, or CONFIG.
Includes the failures-by-test table and the README pool-style limitation note.
Does not invent any cfo.ai API; renders markdown for human copy-paste into cfo.ai.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import verdict

REQUEST_MARKER = "## Request for CFO plan"


def _fmt(v: Any, kind: str = "num") -> str:
    """Format numeric values cleanly."""
    if v is None:
        return "n/a"
    if kind == "pct":
        return f"{v:.2f}"
    if kind == "usd":
        return f"${v:.6f}"
    if kind == "int":
        return f"{int(round(v))}"
    if kind == "currency_inr":
        return f"{v:.2f} INR"
    return f"{v:.2f}"


def _format_with_baseline(val: Any, base_val: Any, kind: str, tag: str) -> str:
    """Format a metric value with its baseline comparison and tag."""
    val_str = f"{_fmt(val, kind)} [{tag}]"
    if base_val is not None:
        return f"{val_str} (baseline: {_fmt(base_val, kind)} [{tag}])"
    return val_str


def _detect_founder_source(founder: dict) -> str:
    """Infer founder filename from profile content when not explicitly passed."""
    budget = founder.get("budget_inr")
    demand = str(founder.get("demand_evidence", "")).strip().lower()
    if budget == 350000:
        return "founder_b.yaml" if demand == "none" else "founder_a.yaml"
    if budget == 250000:
        return "founder.yaml"
    return "founder_a.yaml"


def pick_arm(metrics: dict, cohort: str = "held_out") -> tuple[str, dict, dict]:
    """Pick the primary headline arm and baseline arm for the given cohort."""
    exp = metrics.get("experiment", {})
    cohort_data = exp.get(cohort, {})
    arm = cohort_data.get("improved")
    baseline_arm = cohort_data.get("baseline", {})
    if arm and arm.get("n_runs"):
        return f"improved arm, {cohort} cohort", arm, baseline_arm

    for c in ["held_out", "tuning", "combined"]:
        candidate = exp.get(c, {}).get("improved")
        if candidate and candidate.get("n_runs"):
            return f"improved arm, {c} cohort", candidate, exp.get(c, {}).get("baseline", {})

    return "all real runs (live)", metrics.get("live", metrics), {}


def render(
    metrics: dict,
    assumptions: dict,
    founder: dict | None = None,
    cohort: str = "held_out",
    founder_source: str | None = None,
) -> str:
    """Render the full cfo_input.md content with all numbers labeled."""
    if founder is None:
        fp = verdict.resolve_founder_path("a")
        founder = verdict.load_founder_profile(fp)
        founder_source = fp.name
    elif founder_source is None:
        founder_source = _detect_founder_source(founder)

    label, arm, baseline_arm = pick_arm(metrics, cohort=cohort)

    # Evaluate verdict layers to get computed gross margin & runway
    verdict_res = verdict.compute(arm, assumptions, founder)
    inputs = verdict_res["inputs"]

    target_user = founder.get("target_user", "target user")

    lines = [
        f"Founder file: {founder_source}, cohort: {cohort}",
        "",
        "I am planning pricing, costs, revenue and runway for an AI agent product called Pocket Startup. It turns a startup idea into a tested single-file web app plus a viability verdict.",
        f"The unit of sale is one run: one tested single-file app build delivered to a customer; the customer is {target_user}; price is per run in INR.",
        "Every figure below carries a tag: MEASURED (from traced runs), COMPUTED (from list price, formulas or conversions), USER-PROVIDED (from founder input) or ASSUMED (business assumptions).",
        "",
        f"## Measured and computed metrics ({label})",
        f"- runs analysed: {_fmt(arm.get('n_runs'), 'int')} [MEASURED]",
        f"- success rate: {_format_with_baseline(arm.get('success_rate'), baseline_arm.get('success_rate'), 'pct', 'MEASURED')}",
        f"- first-attempt pass rate: {_format_with_baseline(arm.get('first_attempt_pass_rate'), baseline_arm.get('first_attempt_pass_rate'), 'pct', 'MEASURED')}",
        f"- average tokens per run: {_fmt(arm.get('avg_tokens'), 'int')} [MEASURED]",
        f"- median latency per run in seconds: {_fmt(arm.get('median_latency_s'))} [MEASURED]",
        f"- cost per successful build: {_format_with_baseline(arm.get('cost_per_success'), baseline_arm.get('cost_per_success'), 'usd', 'COMPUTED')}",
        f"- retry tax (share of cost spent after first attempt): {_format_with_baseline(arm.get('retry_tax'), baseline_arm.get('retry_tax'), 'pct', 'COMPUTED')}",
        "",
        "## Failures by test",
    ]

    # Add failures-by-test breakdown for the selected cohort
    exp = metrics.get("experiment", {})
    cohort_data = exp.get(cohort, {})
    baseline_cohort = cohort_data.get("baseline", {}).get("failures_by_test", {})
    improved_cohort = cohort_data.get("improved", {}).get("failures_by_test", {})

    if not baseline_cohort and not improved_cohort and exp.get("combined"):
        baseline_cohort = exp.get("combined", {}).get("baseline", {}).get("failures_by_test", {})
        improved_cohort = exp.get("combined", {}).get("improved", {}).get("failures_by_test", {})

    if baseline_cohort:
        for tname, count in sorted(baseline_cohort.items()):
            lines.append(f"- baseline {tname} failures: {count} [MEASURED]")
    else:
        lines.append("- baseline test failures: 0 [MEASURED]")

    if improved_cohort:
        for tname, count in sorted(improved_cohort.items()):
            lines.append(f"- improved {tname} failures: {count} [MEASURED]")
    else:
        lines.append("- improved test failures: 0 [MEASURED]")

    lines += [
        "",
        "## Known limitation on pool-style ideas",
        (
            "- known limitation note: pool-style ideas (e.g. SalonPool Tips) failed split_basic with actual "
            "$5.00 [MEASURED] vs expected $30.00 [CONFIG] (manual founder observation was $20.00 [USER-PROVIDED]), "
            "because template notes specify a per-person total bill amount while pool ideas distribute the tip pool only [OBSERVATION]"
        ),
        "",
        "## Founder profile",
        f"- target user: {founder.get('target_user')} [USER-PROVIDED]",
        f"- payer: {founder.get('payer')} [USER-PROVIDED]",
        f"- starting budget: {founder.get('budget_inr')} INR [USER-PROVIDED]",
        f"- weekly hours: {founder.get('weekly_hours')} hours per week [USER-PROVIDED]",
        f"- skills: {', '.join(founder.get('skills', [])) if isinstance(founder.get('skills'), list) else founder.get('skills')} [USER-PROVIDED]",
        f"- goal: {founder.get('goal')} [USER-PROVIDED]",
        f"- first customer channel: {founder.get('first_customer_channel')} [USER-PROVIDED]",
        f"- demand evidence: {founder.get('demand_evidence')} [USER-PROVIDED]",
        f"- customer price per run: {founder.get('price_per_run_inr')} INR [USER-PROVIDED]",
        "",
        "## Business assumptions",
        f"- currency conversion rate (usd to inr): {_fmt(assumptions.get('usd_inr', 85.0))} [ASSUMED]",
        f"- infrastructure cost per run: ${_fmt(assumptions.get('infra_per_run_usd', 0.02))} [ASSUMED]",
        f"- fixed monthly operating costs: {assumptions.get('fixed_monthly_inr', 20000)} INR [ASSUMED]",
        f"- runs per customer per month: {assumptions.get('runs_per_customer_per_month', 20)} [ASSUMED]",
        f"- customers in month one: {assumptions.get('customers_month_1', 10)} [ASSUMED]",
        f"- customers in month twelve: {assumptions.get('customers_month_12', 200)} [ASSUMED]",
        "",
        "## Pocket Startup's own estimates, for comparison only",
        f"- gross margin: {_fmt(inputs['gross_margin']['value'], 'pct')} [COMPUTED]",
        f"- runway: {_fmt(inputs['runway_months']['value'])} months [COMPUTED]",
        "",
        REQUEST_MARKER,
        (
            "Produce: three pricing options with a recommendation, unit economics, gross margin, "
            "twelve-month projections in base and growth scenarios, runway, and the assumptions that "
            "change the outcome most. Keep the MEASURED, COMPUTED, USER-PROVIDED and ASSUMED tags on "
            "every number you report. If you introduce any number that is not in this file, label it "
            "[CFO.AI-ASSUMED] and list those numbers separately."
        ),
        "",
    ]

    return "\n".join(lines)


def write(
    metrics_path: Path | str | None = None,
    assumptions_path: Path | str | None = None,
    founder_path: Path | str | None = None,
    out_path: Path | str | None = None,
    cohort: str = "held_out",
    founder: str | Path | dict | None = None,
) -> Path:
    """Render and write evidence/cfo/cfo_input.md."""
    mp = Path(metrics_path or config.METRICS_PATH)
    if not mp.exists() and (config.ROOT / "evidence" / "metrics.json").exists():
        mp = config.ROOT / "evidence" / "metrics.json"
    metrics = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}

    assumptions = config.load_assumptions(assumptions_path)

    founder_arg = founder if founder is not None else founder_path
    if isinstance(founder_arg, dict):
        founder_profile = founder_arg
        founder_source = _detect_founder_source(founder_profile)
    else:
        fp = verdict.resolve_founder_path(founder_arg)
        founder_profile = verdict.load_founder_profile(fp)
        founder_source = fp.name

    text = render(metrics, assumptions, founder=founder_profile, cohort=cohort, founder_source=founder_source)
    out = Path(out_path or config.CFO_DIR / "cfo_input.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint to render cfo_input.md with the same arguments as verdict.py."""
    parser = argparse.ArgumentParser(description="Render cfo_input.md from metrics, assumptions, and founder profile.")
    parser.add_argument(
        "--founder",
        default="a",
        help="Founder profile to load: 'a', 'b', 'base', or path to founder YAML (default: a)",
    )
    parser.add_argument(
        "--cohort",
        choices=["held_out", "tuning", "combined"],
        default="held_out",
        help="Evaluation cohort from metrics.json (default: held_out)",
    )
    parser.add_argument(
        "--metrics",
        default=None,
        help="Path to metrics.json (default: evidence/metrics.json)",
    )
    parser.add_argument(
        "--assumptions",
        default=None,
        help="Path to assumptions.yaml (default: assumptions.yaml)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Path to output cfo_input.md (default: evidence/cfo/cfo_input.md)",
    )

    args = parser.parse_args(argv)

    fp = verdict.resolve_founder_path(args.founder)
    print(f"Founder file: {fp.name}, cohort: {args.cohort}")

    written_path = write(
        metrics_path=args.metrics,
        assumptions_path=args.assumptions,
        founder_path=fp,
        out_path=args.out,
        cohort=args.cohort,
    )
    print(f"wrote {written_path}")


if __name__ == "__main__":
    main()
