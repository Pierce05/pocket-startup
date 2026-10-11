"""Deterministic, layered BUILD / PIVOT / KILL verdict rules engine. No LLM involved.

Layers:
1. Technical (MEASURED: first-attempt rate, eventual success, retry tax)
2. Economics (COMPUTED: gross margin from measured cost per success converted at usd_inr)
3. Founder Fit (COMPUTED: runway months = budget / (fixed monthly + expected monthly variable cost))
4. Demand Cap (demand_evidence 'none' caps the verdict at PIVOT)

The overall verdict is the most restrictive layer (KILL > PIVOT > BUILD).
"""
import argparse
import json
from pathlib import Path
import sys
from typing import Any

import yaml

import config

SEVERITY = {
    "BUILD": 1,
    "PIVOT": 2,
    "KILL": 3,
}

CHEAPEST_NEXT_EXPERIMENTS = {
    "demand_evidence_none": {
        "experiment": "Conduct 5 problem discovery interviews with target users before writing code",
        "estimated_cost": "0 INR / 5 hours [ASSUMED]",
        "lever": "conduct customer interviews to validate demand before building",
    },
    "technical_success_rate": {
        "experiment": "Evaluate prompt edge-case rules on tuning set with Playwright acceptance checks",
        "estimated_cost": "42.50 INR ($0.50 LLM API calls) [ASSUMED]",
        "lever": "tighter prompt or stronger model to improve success rate",
    },
    "technical_retry_tax": {
        "experiment": "Add pre-generation edge-case validation checklist to builder prompt",
        "estimated_cost": "42.50 INR ($0.50 LLM API calls) [ASSUMED]",
        "lever": "tighter builder prompt so fewer builds require retries",
    },
    "economics_margin": {
        "experiment": "Test higher pricing tier with 3 prospective buyers or reduce infra overhead",
        "estimated_cost": "0 INR / 2 hours [ASSUMED]",
        "lever": "higher price, cheaper model, or reduced infra overhead",
    },
    "founder_runway": {
        "experiment": "Secure 1 pre-paid pilot customer or reduce monthly fixed subscriptions",
        "estimated_cost": "0 INR / 3 hours [ASSUMED]",
        "lever": "lower fixed costs or obtain upfront customer pilot deposits",
    },
    "all_clear_build": {
        "experiment": "Deploy MVP to initial cohort of 10 pilot users and measure 7-day retention",
        "estimated_cost": "200 INR per month infra [ASSUMED]",
        "lever": "proceed to MVP build and customer onboarding",
    },
    "no_successes": {
        "experiment": "Run 3 diagnostic smoke test runs with neatlogs trace logging enabled",
        "estimated_cost": "12.75 INR ($0.15 LLM API calls) [ASSUMED]",
        "lever": "investigate baseline model failure modes",
    },
}

REQUIRED_FOUNDER_KEYS = {
    "target_user",
    "payer",
    "budget_inr",
    "weekly_hours",
    "skills",
    "goal",
    "first_customer_channel",
    "demand_evidence",
    "price_per_run_inr",
}

VALID_DEMAND_EVIDENCE = {"none", "interviews", "waitlist", "paid_pilot"}


def validate_founder(profile: dict) -> None:
    """Validate founder profile schema."""
    if not isinstance(profile, dict):
        raise ValueError("Founder profile must be a dictionary.")
    missing = REQUIRED_FOUNDER_KEYS - set(profile.keys())
    if missing:
        raise ValueError(f"Founder profile missing required keys: {sorted(missing)}")
    evidence = str(profile.get("demand_evidence", "")).strip().lower()
    if evidence not in VALID_DEMAND_EVIDENCE:
        raise ValueError(f"Invalid demand_evidence '{evidence}'. Must be one of {sorted(VALID_DEMAND_EVIDENCE)}")


def load_founder_profile(path: Path | str | None = None) -> dict:
    """Load and validate founder profile YAML."""
    p = Path(path) if path else config.FOUNDER_PATH
    content = yaml.safe_load(p.read_text(encoding="utf-8"))
    validate_founder(content)
    return content


def gross_margin(
    price_inr: float | None,
    cost_per_success_usd: float | None,
    infra_per_run_usd: float = 0.02,
    usd_inr: float = 85.0,
) -> float | None:
    """Compute gross margin from price and variable cost converted to INR."""
    if price_inr is None or price_inr <= 0 or cost_per_success_usd is None:
        return None
    cost_per_run_inr = (cost_per_success_usd + infra_per_run_usd) * usd_inr
    return (price_inr - cost_per_run_inr) / price_inr


def calculate_runway(
    budget_inr: float | None,
    fixed_monthly_inr: float,
    expected_monthly_runs: int,
    cost_per_run_inr: float,
) -> tuple[float | None, float]:
    """Calculate runway in months and total monthly burn in INR."""
    if budget_inr is None:
        return None, fixed_monthly_inr
    monthly_var_cost = expected_monthly_runs * cost_per_run_inr
    monthly_burn = fixed_monthly_inr + monthly_var_cost
    if monthly_burn <= 0:
        return float("inf"), monthly_burn
    return budget_inr / monthly_burn, monthly_burn


def compute(
    metrics_arm: dict | None,
    assumptions: dict | None,
    founder: dict | None = None,
) -> dict[str, Any]:
    """Deterministic, layered BUILD / PIVOT / KILL evaluation.

    Args:
        metrics_arm: Aggregate metrics dict (or None)
        assumptions: Assumptions dict containing thresholds and business parameters
        founder: Founder profile dict (or None, in which case default is loaded)
    """
    if assumptions is None:
        assumptions = config.load_assumptions()
    if founder is None:
        try:
            founder = load_founder_profile()
        except Exception:
            founder = {
                "target_user": "Default Target",
                "payer": "Default Payer",
                "budget_inr": 250000,
                "weekly_hours": 30,
                "skills": ["product"],
                "goal": "Launch MVP",
                "first_customer_channel": "Direct outreach",
                "demand_evidence": "interviews",
                "price_per_run_inr": 50.0,
            }

    arm = metrics_arm or {}
    th = assumptions.get("thresholds", {})

    # Key assumptions
    usd_inr = float(assumptions.get("usd_inr", 85.0))
    infra_usd = float(assumptions.get("infra_per_run_usd", 0.02))
    fixed_monthly_inr = float(assumptions.get("fixed_monthly_inr", 20000.0))
    runs_per_cust = int(assumptions.get("runs_per_customer_per_month", 20))
    c1 = int(assumptions.get("customers_month_1", 10))
    monthly_runs = c1 * runs_per_cust

    # Thresholds
    kill_sr = float(th.get("kill_success_rate", 0.5))
    build_sr = float(th.get("build_success_rate", 0.8))
    kill_margin = float(th.get("kill_margin", 0.2))
    build_margin = float(th.get("build_margin", 0.6))
    kill_runway = float(th.get("kill_runway_months", 6.0))
    build_runway = float(th.get("build_runway_months", 12.0))
    build_tax = float(th.get("build_retry_tax", 0.35))

    # Metric inputs
    sr = arm.get("success_rate")
    first_pass = arm.get("first_attempt_pass_rate")
    tax = arm.get("retry_tax")
    cps_usd = arm.get("cost_per_success")

    # Founder inputs
    price_inr = float(founder.get("price_per_run_inr", 50.0)) if founder.get("price_per_run_inr") is not None else None
    budget_inr = float(founder.get("budget_inr", 250000.0)) if founder.get("budget_inr") is not None else None
    demand_ev = str(founder.get("demand_evidence", "none")).strip().lower()

    # Derived financial inputs
    cost_per_run_usd = (cps_usd + infra_usd) if cps_usd is not None else infra_usd
    cost_per_run_inr = cost_per_run_usd * usd_inr
    margin = gross_margin(price_inr, cps_usd, infra_usd, usd_inr)
    runway_m, monthly_burn_inr = calculate_runway(budget_inr, fixed_monthly_inr, monthly_runs, cost_per_run_inr)

    reasons: list[str] = []
    layer_verdicts: dict[str, str] = {}
    primary_failure_key = None

    # ---- Layer 1: Technical (MEASURED: first-attempt rate, eventual success, retry tax) ----
    if sr is None or cps_usd is None:
        tech_v = "PIVOT"
        reasons.append("Technical: zero successful runs measured; cost per success is unknown [MEASURED]")
        if primary_failure_key is None:
            primary_failure_key = "no_successes"
    elif sr < kill_sr:
        tech_v = "KILL"
        reasons.append(f"Technical: success rate {sr:.2f} [MEASURED] is below kill threshold {kill_sr:.2f} [ASSUMED]")
        if primary_failure_key is None:
            primary_failure_key = "technical_success_rate"
    else:
        sr_pass = sr >= build_sr
        tax_pass = (tax is not None and tax <= build_tax)
        if sr_pass and tax_pass:
            tech_v = "BUILD"
            fp_str = f"{first_pass:.2f}" if first_pass is not None else "n/a"
            reasons.append(
                f"Technical: success rate {sr:.2f} [MEASURED] >= {build_sr:.2f} [ASSUMED], "
                f"retry tax {tax:.2f} [COMPUTED] <= {build_tax:.2f} [ASSUMED], "
                f"first-attempt pass rate {fp_str} [MEASURED]"
            )
        else:
            tech_v = "PIVOT"
            if not sr_pass:
                reasons.append(f"Technical: success rate {sr:.2f} [MEASURED] is below build threshold {build_sr:.2f} [ASSUMED]")
                if primary_failure_key is None:
                    primary_failure_key = "technical_success_rate"
            if not tax_pass and tax is not None:
                reasons.append(f"Technical: retry tax {tax:.2f} [COMPUTED] exceeds build limit {build_tax:.2f} [ASSUMED]")
                if primary_failure_key is None:
                    primary_failure_key = "technical_retry_tax"
    layer_verdicts["technical"] = tech_v

    # ---- Layer 2: Economics (COMPUTED: gross margin from measured cost per success at usd_inr) ----
    if margin is None:
        econ_v = "PIVOT"
        reasons.append("Economics: gross margin cannot be computed due to missing price or cost per success [COMPUTED]")
        if primary_failure_key is None:
            primary_failure_key = "economics_margin"
    elif margin < kill_margin:
        econ_v = "KILL"
        reasons.append(
            f"Economics: gross margin {margin:.2f} [COMPUTED] is below kill threshold {kill_margin:.2f} [ASSUMED] "
            f"(price {price_inr:.2f} INR [USER-PROVIDED], cost per run {cost_per_run_inr:.2f} INR [COMPUTED])"
        )
        if primary_failure_key is None:
            primary_failure_key = "economics_margin"
    elif margin >= build_margin:
        econ_v = "BUILD"
        reasons.append(
            f"Economics: gross margin {margin:.2f} [COMPUTED] >= {build_margin:.2f} [ASSUMED] "
            f"(price {price_inr:.2f} INR [USER-PROVIDED], cost per run {cost_per_run_inr:.2f} INR [COMPUTED])"
        )
    else:
        econ_v = "PIVOT"
        reasons.append(
            f"Economics: gross margin {margin:.2f} [COMPUTED] is below build threshold {build_margin:.2f} [ASSUMED] "
            f"(price {price_inr:.2f} INR [USER-PROVIDED], cost per run {cost_per_run_inr:.2f} INR [COMPUTED])"
        )
        if primary_failure_key is None:
            primary_failure_key = "economics_margin"
    layer_verdicts["economics"] = econ_v

    # ---- Layer 3: Founder Fit (COMPUTED: runway months = budget / (fixed monthly + expected monthly variable cost)) ----
    if runway_m is None:
        fit_v = "PIVOT"
        reasons.append("Founder Fit: budget is missing; runway cannot be computed [COMPUTED]")
        if primary_failure_key is None:
            primary_failure_key = "founder_runway"
    elif runway_m < kill_runway:
        fit_v = "KILL"
        reasons.append(
            f"Founder Fit: runway {runway_m:.1f} months [COMPUTED] is below kill threshold {kill_runway:.1f} months [ASSUMED] "
            f"(budget {budget_inr:.0f} INR [USER-PROVIDED], monthly burn {monthly_burn_inr:.1f} INR [COMPUTED])"
        )
        if primary_failure_key is None:
            primary_failure_key = "founder_runway"
    elif runway_m >= build_runway:
        fit_v = "BUILD"
        reasons.append(
            f"Founder Fit: runway {runway_m:.1f} months [COMPUTED] >= {build_runway:.1f} months [ASSUMED] "
            f"(budget {budget_inr:.0f} INR [USER-PROVIDED], monthly burn {monthly_burn_inr:.1f} INR [COMPUTED])"
        )
    else:
        fit_v = "PIVOT"
        reasons.append(
            f"Founder Fit: runway {runway_m:.1f} months [COMPUTED] is below build threshold {build_runway:.1f} months [ASSUMED] "
            f"(budget {budget_inr:.0f} INR [USER-PROVIDED], monthly burn {monthly_burn_inr:.1f} INR [COMPUTED])"
        )
        if primary_failure_key is None:
            primary_failure_key = "founder_runway"
    layer_verdicts["founder_fit"] = fit_v

    # ---- Layer 4: Demand Cap (demand_evidence 'none' caps the verdict at PIVOT) ----
    demand_capped = (demand_ev == "none")
    if demand_capped:
        demand_v = "PIVOT"
        reasons.append("Demand Cap: demand evidence is none [USER-PROVIDED], capping verdict at PIVOT")
        if primary_failure_key is None:
            primary_failure_key = "demand_evidence_none"
    else:
        demand_v = "BUILD"
        reasons.append(f"Demand Cap: demand evidence is {demand_ev} [USER-PROVIDED]")
    layer_verdicts["demand_cap"] = demand_v

    # ---- Most Restrictive Layer Verdict ----
    max_sev = max(SEVERITY[v] for v in [tech_v, econ_v, fit_v])
    rev_severity = {1: "BUILD", 2: "PIVOT", 3: "KILL"}
    tentative_v = rev_severity[max_sev]

    if tentative_v == "BUILD" and demand_capped:
        final_verdict = "PIVOT"
        primary_failure_key = "demand_evidence_none"
    else:
        final_verdict = tentative_v

    if final_verdict == "BUILD":
        primary_failure_key = "all_clear_build"

    exp_template = CHEAPEST_NEXT_EXPERIMENTS.get(
        primary_failure_key or "all_clear_build",
        CHEAPEST_NEXT_EXPERIMENTS["all_clear_build"],
    )
    cheapest_experiment = dict(exp_template)
    if primary_failure_key in ("technical_success_rate", "technical_retry_tax"):
        inr = 0.50 * usd_inr
        cheapest_experiment["estimated_cost"] = f"{inr:.2f} INR ($0.50 LLM API calls) [ASSUMED]"
    elif primary_failure_key == "no_successes":
        inr = 0.15 * usd_inr
        cheapest_experiment["estimated_cost"] = f"{inr:.2f} INR ($0.15 LLM API calls) [ASSUMED]"

    inputs_summary = {
        "success_rate": {"value": sr, "tag": "MEASURED"},
        "first_attempt_pass_rate": {"value": first_pass, "tag": "MEASURED"},
        "retry_tax": {"value": tax, "tag": "COMPUTED"},
        "cost_per_success_usd": {"value": cps_usd, "tag": "COMPUTED"},
        "usd_inr": {"value": usd_inr, "tag": "ASSUMED"},
        "infra_per_run_usd": {"value": infra_usd, "tag": "ASSUMED"},
        "price_per_run_inr": {"value": price_inr, "tag": "USER-PROVIDED"},
        "gross_margin": {"value": margin, "tag": "COMPUTED"},
        "budget_inr": {"value": budget_inr, "tag": "USER-PROVIDED"},
        "fixed_monthly_inr": {"value": fixed_monthly_inr, "tag": "ASSUMED"},
        "monthly_burn_inr": {"value": monthly_burn_inr, "tag": "COMPUTED"},
        "runway_months": {"value": runway_m, "tag": "COMPUTED"},
        "demand_evidence": {"value": demand_ev, "tag": "USER-PROVIDED"},
    }

    return {
        "verdict": final_verdict,
        "layer_verdicts": layer_verdicts,
        "reasons": reasons,
        "cheapest_next_experiment": cheapest_experiment,
        "inputs": inputs_summary,
        "thresholds": th,
    }


def compute_verdict(metrics_arm: dict | None, assumptions: dict | None, founder: dict | None = None) -> dict[str, Any]:
    """Alias for compute."""
    return compute(metrics_arm, assumptions, founder)


def generate_ledger(
    metrics_path: Path | str | None = None,
    assumptions_path: Path | str | None = None,
    founder_path: Path | str | None = None,
    out_path: Path | str | None = None,
) -> dict:
    """Generate evidence/ledger.json containing every input with value, tag, and source."""
    mp = Path(metrics_path or config.METRICS_PATH)
    ap = Path(assumptions_path or config.ASSUMPTIONS_PATH)
    fp = Path(founder_path or config.FOUNDER_PATH)

    metrics = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    assumptions = yaml.safe_load(ap.read_text(encoding="utf-8")) if ap.exists() else {}
    founder = yaml.safe_load(fp.read_text(encoding="utf-8")) if fp.exists() else {}

    # Prefer improved arm from headline held_out or combined
    exp = metrics.get("experiment", {})
    arm = exp.get("combined", {}).get("improved") or exp.get("held_out", {}).get("improved") or {}

    ledger = {
        # MEASURED metrics
        "n_runs": {
            "value": arm.get("n_runs"),
            "tag": "MEASURED",
            "source": str(mp.name),
        },
        "success_rate": {
            "value": arm.get("success_rate"),
            "tag": "MEASURED",
            "source": str(mp.name),
        },
        "first_attempt_pass_rate": {
            "value": arm.get("first_attempt_pass_rate"),
            "tag": "MEASURED",
            "source": str(mp.name),
        },
        "avg_tokens": {
            "value": arm.get("avg_tokens"),
            "tag": "MEASURED",
            "source": str(mp.name),
        },
        "median_latency_s": {
            "value": arm.get("median_latency_s"),
            "tag": "MEASURED",
            "source": str(mp.name),
        },
        "failures_by_test": {
            "value": arm.get("failures_by_test", {}),
            "tag": "MEASURED",
            "source": str(mp.name),
        },
        # COMPUTED metrics
        "cost_per_success": {
            "value": arm.get("cost_per_success"),
            "tag": "COMPUTED",
            "source": str(mp.name),
        },
        "retry_tax": {
            "value": arm.get("retry_tax"),
            "tag": "COMPUTED",
            "source": str(mp.name),
        },
        # CONFIG / METADATA
        "model": {
            "value": arm.get("model") or metrics.get("meta", {}).get("model") or "unknown",
            "tag": "CONFIG",
            "source": str(mp.name),
        },
        "pricing_date": {
            "value": arm.get("pricing_date", metrics.get("meta", {}).get("pricing_date", "2026-10-11")),
            "tag": "CONFIG",
            "source": str(mp.name),
        },
        # ASSUMED business parameters
        "usd_inr": {
            "value": assumptions.get("usd_inr", 85.0),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "infra_per_run_usd": {
            "value": assumptions.get("infra_per_run_usd", 0.02),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "fixed_monthly_inr": {
            "value": assumptions.get("fixed_monthly_inr", 20000),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "runs_per_customer_per_month": {
            "value": assumptions.get("runs_per_customer_per_month", 20),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "customers_month_1": {
            "value": assumptions.get("customers_month_1", 10),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "customers_month_12": {
            "value": assumptions.get("customers_month_12", 200),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        # ASSUMED thresholds
        "kill_success_rate": {
            "value": assumptions.get("thresholds", {}).get("kill_success_rate", 0.5),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "build_success_rate": {
            "value": assumptions.get("thresholds", {}).get("build_success_rate", 0.8),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "kill_margin": {
            "value": assumptions.get("thresholds", {}).get("kill_margin", 0.2),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "build_margin": {
            "value": assumptions.get("thresholds", {}).get("build_margin", 0.6),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "kill_runway_months": {
            "value": assumptions.get("thresholds", {}).get("kill_runway_months", 6),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "build_runway_months": {
            "value": assumptions.get("thresholds", {}).get("build_runway_months", 12),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        "build_retry_tax": {
            "value": assumptions.get("thresholds", {}).get("build_retry_tax", 0.35),
            "tag": "ASSUMED",
            "source": str(ap.name),
        },
        # USER-PROVIDED founder profile inputs
        "target_user": {
            "value": founder.get("target_user"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "payer": {
            "value": founder.get("payer"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "budget_inr": {
            "value": founder.get("budget_inr"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "weekly_hours": {
            "value": founder.get("weekly_hours"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "skills": {
            "value": founder.get("skills"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "goal": {
            "value": founder.get("goal"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "first_customer_channel": {
            "value": founder.get("first_customer_channel"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "demand_evidence": {
            "value": founder.get("demand_evidence"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
        "price_per_run_inr": {
            "value": founder.get("price_per_run_inr"),
            "tag": "USER-PROVIDED",
            "source": str(fp.name),
        },
    }

    out = Path(out_path or config.LEDGER_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return ledger


COHORT_SELECTION_REASONS = {
    "held_out": "conservative choice for ideas the patch never saw",
    "tuning": "diagnostic choice for ideas used during prompt patch tuning",
    "combined": "aggregate choice across all evaluation ideas (tuning + held-out)",
}


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint to run verdict evaluation for a specified founder and cohort."""
    parser = argparse.ArgumentParser(description="Run deterministic verdict evaluation.")
    parser.add_argument(
        "--founder",
        default="a",
        help="Founder profile to load: 'a', 'b', or path to founder YAML (default: a)",
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

    args = parser.parse_args(argv)

    # Resolve founder profile path
    founder_arg = str(args.founder).strip()
    if founder_arg.lower() in ("a", "founder_a"):
        fp = config.ROOT / "founder_a.yaml"
    elif founder_arg.lower() in ("b", "founder_b"):
        fp = config.ROOT / "founder_b.yaml"
    elif Path(founder_arg).exists():
        fp = Path(founder_arg)
    elif (config.ROOT / founder_arg).exists():
        fp = config.ROOT / founder_arg
    elif (config.ROOT / f"founder_{founder_arg}.yaml").exists():
        fp = config.ROOT / f"founder_{founder_arg}.yaml"
    else:
        fp = config.FOUNDER_PATH

    founder_profile = load_founder_profile(fp)
    assumptions = config.load_assumptions(args.assumptions)

    mp = Path(args.metrics or config.METRICS_PATH)
    if not mp.exists() and (config.ROOT / "evidence" / "metrics.json").exists():
        mp = config.ROOT / "evidence" / "metrics.json"
    metrics = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    arm = metrics.get("experiment", {}).get(args.cohort, {}).get("improved", {})

    res = compute(arm, assumptions, founder_profile)

    cohort_reason = COHORT_SELECTION_REASONS.get(args.cohort, "selected evaluation cohort")

    print(f"Verdict: {res['verdict']}")
    print(
        f"Cohort fed to technical layer: improved arm, {args.cohort} cohort of evidence/metrics.json "
        f"(chosen because that is the {cohort_reason})."
    )
    print("Reasons:")
    for r in res["reasons"]:
        print(f"  - {r}")
    exp_info = res["cheapest_next_experiment"]
    print("Cheapest Next Experiment:")
    print(f"  - Experiment: {exp_info.get('experiment')}")
    print(f"  - Estimated Cost: {exp_info.get('estimated_cost')}")
    print(f"  - Lever: {exp_info.get('lever')}")


if __name__ == "__main__":
    main()

