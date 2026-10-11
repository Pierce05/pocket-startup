"""Render evidence/cfo/cfo_input.md from metrics.json, assumptions.yaml, and founder.yaml.

Every number carries an explicit tag: MEASURED, COMPUTED, USER-PROVIDED, or ASSUMED.
Includes the failures-by-test table and the README pool-style limitation note.
Does not invent any cfo.ai API; renders markdown for human copy-paste into cfo.ai.
"""
import json
import re
from pathlib import Path
from typing import Any

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


def pick_arm(metrics: dict) -> tuple[str, dict]:
    """Pick the primary headline arm to evaluate."""
    exp = metrics.get("experiment", {})
    for label, path in [
        ("improved arm, combined sets", ("combined", "improved")),
        ("improved arm, held-out set", ("held_out", "improved")),
        ("improved arm, tuning set", ("tuning", "improved")),
    ]:
        arm = exp.get(path[0], {}).get(path[1])
        if arm and arm.get("n_runs"):
            return label, arm
    return "all real runs (live)", metrics.get("live", {})


def render(
    metrics: dict,
    assumptions: dict,
    founder: dict | None = None,
) -> str:
    """Render the full cfo_input.md content with all numbers labeled."""
    if founder is None:
        founder = config.load_founder()

    label, arm = pick_arm(metrics)
    th = assumptions.get("thresholds", {})

    # Evaluate verdict layers to get computed gross margin & runway
    verdict_res = verdict.compute(arm, assumptions, founder)
    inputs = verdict_res["inputs"]

    lines = [
        "I am planning pricing, costs, revenue and runway for an AI agent product called Pocket Startup. It turns a startup idea into a tested single-file web app plus a viability verdict.",
        "Every figure below carries a tag: MEASURED (from traced runs), COMPUTED (from list price, formulas or conversions), USER-PROVIDED (from founder input) or ASSUMED (business assumptions).",
        "",
        f"## Measured and computed metrics ({label})",
        f"- runs analysed: {_fmt(arm.get('n_runs'), 'int')} [MEASURED]",
        f"- success rate: {_fmt(arm.get('success_rate'), 'pct')} [MEASURED]",
        f"- first-attempt pass rate: {_fmt(arm.get('first_attempt_pass_rate'), 'pct')} [MEASURED]",
        f"- average tokens per run: {_fmt(arm.get('avg_tokens'), 'int')} [MEASURED]",
        f"- median latency per run in seconds: {_fmt(arm.get('median_latency_s'))} [MEASURED]",
        f"- cost per successful build: {_fmt(arm.get('cost_per_success'), 'usd')} [COMPUTED]",
        f"- retry tax (share of cost spent after first attempt): {_fmt(arm.get('retry_tax'), 'pct')} [COMPUTED]",
        f"- gross margin: {_fmt(inputs['gross_margin']['value'], 'pct')} [COMPUTED]",
        f"- runway: {_fmt(inputs['runway_months']['value'])} months [COMPUTED]",
        "",
        "## Failures by test",
    ]

    # Add failures-by-test breakdown from metrics
    exp = metrics.get("experiment", {})
    baseline_combined = exp.get("combined", {}).get("baseline", {}).get("failures_by_test", {})
    improved_combined = exp.get("combined", {}).get("improved", {}).get("failures_by_test", {})

    if baseline_combined:
        for tname, count in sorted(baseline_combined.items()):
            lines.append(f"- baseline {tname} failures: {count} [MEASURED]")
    if improved_combined:
        for tname, count in sorted(improved_combined.items()):
            lines.append(f"- improved {tname} failures: {count} [MEASURED]")
    else:
        lines.append("- improved test failures: 0 [MEASURED]")

    lines += [
        "",
        "## Known limitation on pool-style ideas",
        (
            "- known limitation note: pool-style ideas (e.g. SalonPool Tips) failed split_basic with actual "
            "$5.00 [MEASURED] vs expected $30.00 [ASSUMED] (manual founder observation was $20.00 [USER-PROVIDED]), "
            "because template notes specify a per-person total bill amount while pool ideas distribute the tip pool only [ASSUMED]"
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
        f"- kill threshold for success rate: {_fmt(th.get('kill_success_rate', 0.5), 'pct')} [ASSUMED]",
        f"- build threshold for success rate: {_fmt(th.get('build_success_rate', 0.8), 'pct')} [ASSUMED]",
        f"- kill threshold for gross margin: {_fmt(th.get('kill_margin', 0.2), 'pct')} [ASSUMED]",
        f"- build threshold for gross margin: {_fmt(th.get('build_margin', 0.6), 'pct')} [ASSUMED]",
        f"- kill threshold for runway: {_fmt(th.get('kill_runway_months', 6.0))} months [ASSUMED]",
        f"- build threshold for runway: {_fmt(th.get('build_runway_months', 12.0))} months [ASSUMED]",
        f"- build threshold for retry tax: {_fmt(th.get('build_retry_tax', 0.35), 'pct')} [ASSUMED]",
        "",
        REQUEST_MARKER,
        "Produce: three pricing options with a recommendation, unit economics, gross margin, twelve-month projections in base and growth scenarios, runway, and the assumptions that change the outcome most. Keep the MEASURED, COMPUTED, USER-PROVIDED and ASSUMED tags on every number you report.",
        "",
    ]

    return "\n".join(lines)


def write(
    metrics_path: Path | str | None = None,
    assumptions_path: Path | str | None = None,
    founder_path: Path | str | None = None,
    out_path: Path | str | None = None,
) -> Path:
    """Render and write evidence/cfo/cfo_input.md."""
    mp = Path(metrics_path or config.METRICS_PATH)
    metrics = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}

    assumptions = config.load_assumptions(assumptions_path)
    founder = config.load_founder(founder_path)

    text = render(metrics, assumptions, founder)
    out = Path(out_path or config.CFO_DIR / "cfo_input.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    written_path = write()
    print(f"wrote {written_path}")
