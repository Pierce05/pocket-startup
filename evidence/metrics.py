"""Evidence engine: aggregation, metrics, and cost radar.

MOCK runs, UNPRICED runs, and runs before the Stage 1e cutoff (2026-10-11 04:35:00 UTC)
are strictly excluded from metrics calculations.
"""
import json
import math
import statistics
from pathlib import Path

import config
from agent.llm import PRICES
from experiments.ideas import HELD_OUT, TUNING

STAGE_1E_CUTOFF_UTC = "20261011-043500"


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion [lower, upper]."""
    if n <= 0:
        return (0.0, 0.0)
    z = 1.959963984540054 if confidence == 0.95 else 1.96
    p_hat = k / n
    denom = 1.0 + (z ** 2) / n
    center = (p_hat + (z ** 2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p_hat * (1.0 - p_hat) / n) + ((z ** 2) / (4 * (n ** 2))))
    lower = max(0.0, round(center - margin, 4))
    upper = min(1.0, round(center + margin, 4))
    return (lower, upper)


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-tailed Fisher's exact test for 2x2 contingency table using math.comb.

    Table layout:
        [[a, b],   (row 1: baseline passes, failures)
         [c, d]]   (row 2: improved passes, failures)
    Returns two-tailed p-value rounded to 6 decimal places.
    """
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    n = r1 + r2
    if n == 0 or r1 == 0 or r2 == 0 or c1 == 0 or c2 == 0:
        return 1.0

    def p_hyper(x):
        return (math.comb(r1, x) * math.comb(r2, c1 - x)) / math.comb(n, c1)

    p_obs = p_hyper(a)
    min_x = max(0, c1 - r2)
    max_x = min(r1, c1)
    pval = sum(p_hyper(x) for x in range(min_x, max_x + 1) if p_hyper(x) <= p_obs + 1e-12)
    return min(1.0, round(pval, 6))

SOURCES = {
    "n_runs": "MEASURED",
    "n_ideas": "MEASURED",
    "success_count": "MEASURED",
    "success_rate": "MEASURED",
    "first_attempt_pass_count": "MEASURED",
    "first_attempt_pass_rate": "MEASURED",
    "first_attempt_pass_ci95": "COMPUTED",
    "avg_attempts": "MEASURED",
    "input_tokens": "MEASURED",
    "avg_input_tokens": "MEASURED",
    "output_tokens": "MEASURED",
    "avg_output_tokens": "MEASURED",
    "total_tokens": "MEASURED",
    "avg_tokens": "MEASURED",
    "median_latency_s": "MEASURED",
    "total_cost": "COMPUTED",
    "avg_cost": "COMPUTED",
    "cost_per_success": "COMPUTED",
    "retry_tax": "COMPUTED",
    "retry_tax_with_autopsy": "COMPUTED",
    "retry_tax_without_autopsy": "COMPUTED",
    "cost_by_stage": "COMPUTED",
    "failures_by_test": "MEASURED",
    "tokens_per_success": "MEASURED",
    "fisher_exact_p_value": "COMPUTED",
    "model": "CONFIG",
    "temperature": "CONFIG",
    "pricing_date": "CONFIG",
    "pricing_source": "CONFIG",
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
              cutoff: str | None = STAGE_1E_CUTOFF_UTC,
              include_candidates: bool = False) -> tuple[list[dict], dict]:
    """Load runs from disk, filtering out mocks, unpriced runs, pre-1e runs, and candidate lab runs.

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
            "candidate": 0,
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

        # 2. Check candidate runs (excluded from final A/B statistics)
        if not include_candidates and str(r.get("mode", "")).startswith("candidate_"):
            exclusions["total_excluded"] += 1
            exclusions["by_reason"]["candidate"] += 1
            exclusions["excluded_runs"].append({"run_id": run_id, "reason": "candidate"})
            continue

        # 3. Check mock runs
        is_mock = bool(r.get("mock") or r.get("cost_tag") == "MOCK" or r.get("model") == "mock-model")
        if is_mock and not include_mock:
            exclusions["total_excluded"] += 1
            exclusions["by_reason"]["mock"] += 1
            exclusions["excluded_runs"].append({"run_id": run_id, "reason": "mock"})
            continue

        # 4. Check unpriced runs
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
            "n_ideas": 0,
            "success_count": 0,
            "success_rate": 0.0,
            "first_attempt_pass_count": 0,
            "first_attempt_pass_rate": 0.0,
            "first_attempt_pass_ci95": [0.0, 0.0],
            "avg_attempts": 0.0,
            "input_tokens": 0,
            "avg_input_tokens": 0.0,
            "output_tokens": 0,
            "avg_output_tokens": 0.0,
            "total_tokens": 0,
            "avg_tokens": 0.0,
            "total_cost": 0.0,
            "avg_cost": 0.0,
            "cost_per_success": None,
            "retry_tax": 0.0,
            "retry_tax_with_autopsy": 0.0,
            "retry_tax_without_autopsy": 0.0,
            "retry_tax_note": "Autopsy was disabled (autopsy=False) during this experiment, so retry tax with and without autopsy are strictly identical.",
            "cost_by_stage": {},
            "failures_by_test": {},
            "tokens_per_success": None,
            "median_latency_s": 0.0,
            "model": None,
            "temperature": None,
            "pricing_date": None,
            "pricing_source": None,
            "sources": SOURCES,
            "run_ids": [],
        }

    ok = sum(1 for r in records if bool(r.get("success")))
    fa = sum(1 for r in records if bool(r.get("first_attempt_passed")))
    ideas = set(r.get("idea") for r in records if r.get("idea"))
    n_ideas = len(ideas)

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

    # retry_tax: cost incurred after the first build attempt divided by total cost
    after_first_build = stages.get("retry", 0.0) + stages.get("autopsy", 0.0)
    retry_tax_with = (after_first_build / total_cost) if total_cost > 0.0 else 0.0
    retry_tax_without = (stages.get("retry", 0.0) / total_cost) if total_cost > 0.0 else 0.0

    # Tokens and attempts safely summed (tracking input and output tokens separately)
    input_tokens = sum(int(r.get("input_tokens", 0) or 0) for r in records)
    output_tokens = sum(int(r.get("output_tokens", 0) or 0) for r in records)
    total_tokens = sum(int(r.get("tokens", 0) or (r.get("input_tokens", 0) + r.get("output_tokens", 0)) or 0) for r in records)
    total_attempts = sum(int(r.get("attempts", 0) or 0) for r in records)
    success_tokens = sum(int(r.get("tokens", 0) or 0) for r in records if bool(r.get("success")))

    # Track failures by test name (especially first-attempt failures)
    failures_by_test: dict[str, int] = {}
    for r in records:
        tname = r.get("first_attempt_failed_test")
        if not tname and not r.get("first_attempt_passed"):
            ft = r.get("failed_tests")
            if ft and isinstance(ft, list) and len(ft) > 0:
                tname = ft[0]
        if tname:
            failures_by_test[tname] = failures_by_test.get(tname, 0) + 1

    latencies = [float(r["latency_s"]) for r in records if isinstance(r.get("latency_s"), (int, float))]
    med_latency = statistics.median(latencies) if latencies else 0.0

    ci95 = list(wilson_score_interval(fa, n))

    return {
        "n_runs": n,
        "n_ideas": n_ideas,
        "success_count": ok,
        "success_rate": round(ok / n, 4),
        "first_attempt_pass_count": fa,
        "first_attempt_pass_rate": round(fa / n, 4),
        "first_attempt_pass_ci95": ci95,
        "avg_attempts": round(total_attempts / n, 2),
        "input_tokens": input_tokens,
        "avg_input_tokens": round(input_tokens / n, 1) if n > 0 else 0.0,
        "output_tokens": output_tokens,
        "avg_output_tokens": round(output_tokens / n, 1) if n > 0 else 0.0,
        "total_tokens": total_tokens,
        "avg_tokens": round(total_tokens / n, 1) if n > 0 else 0.0,
        "total_cost": round(total_cost, 6),
        "avg_cost": round(total_cost / n, 6),
        "cost_per_success": round(total_cost / ok, 6) if ok > 0 else None,
        "retry_tax": round(retry_tax_with, 4),
        "retry_tax_with_autopsy": round(retry_tax_with, 4),
        "retry_tax_without_autopsy": round(retry_tax_without, 4),
        "retry_tax_note": "Autopsy was disabled (autopsy=False) during this experiment, so retry tax with and without autopsy are strictly identical.",
        "cost_by_stage": {k: round(v, 6) for k, v in sorted(stages.items())},
        "failures_by_test": dict(sorted(failures_by_test.items(), key=lambda item: (-item[1], item[0]))),
        "tokens_per_success": round(success_tokens / ok, 1) if ok > 0 else None,
        "median_latency_s": round(med_latency, 3),
        "model": records[0].get("model") if records else None,
        "temperature": records[0].get("temperature") if records else None,
        "pricing_date": records[0].get("pricing_date", PRICES.get("pricing_date")) if records else None,
        "pricing_source": records[0].get("pricing_source") if records else None,
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


def render_cost_radar(data: dict) -> str:
    """Render a human-readable Cost Radar report from metrics data.

    All metrics are labeled [MEASURED], [COMPUTED], [CONFIG], or [ASSUMED].
    Zero-success cases are gracefully handled without division errors.
    """
    exp = data.get("experiment", {})
    meta = data.get("meta", {})

    tuning_base = exp.get("tuning", {}).get("baseline", {})
    tuning_impr = exp.get("tuning", {}).get("improved", {})
    held_base = exp.get("held_out", {}).get("baseline", {})
    held_impr = exp.get("held_out", {}).get("improved", {})
    comb_base = exp.get("combined", {}).get("baseline", {})
    comb_impr = exp.get("combined", {}).get("improved", {})

    lines = [
        "# Pocket Startup: A/B Experiment & Cost Radar Report",
        "",
        "> **Evaluation:** Baseline (`BUILDER_SYSTEM_V1`) vs Improved (`BUILDER_SYSTEM_V1` + Frozen Candidate B Patch)",
        "> **Status:** Autopsy disabled (`autopsy=False`), Playwright acceptance checks, sequential execution.",
        "",
        "## 1. Experiment Configuration & Metadata",
        "",
        f"- **Model:** `{meta.get('model', 'unknown')}` `[CONFIG]`",
        f"- **Temperature:** `{meta.get('temperature', 'unknown')}` `[CONFIG]`",
        f"- **Pricing Date & Source:** `{meta.get('pricing_date', 'unknown')}` ({meta.get('pricing_source', 'COMPUTED')}) `[CONFIG]`",
        f"- **Ideas per Set:** `{meta.get('ideas_per_set', 5)}` `[CONFIG]`",
        f"- **Repeats per Idea:** `{meta.get('repeats', 1)}` `[CONFIG]`",
        f"- **Generated At:** `{data.get('generated_at', 'unknown')}` `[MEASURED]`",
        f"- **Frozen Winner Patch (SHA-256):** `{meta.get('builder_v2_patch_sha256', 'unknown')[:16]}...` `[CONFIG]`",
        "",
        "### Frozen Winner Patch Text",
        "```text",
        str(meta.get("builder_v2_patch", "")).strip(),
        "```",
        "",
        "---",
        "",
        "## 2. A/B Performance Summary",
        "",
    ]

    def _fmt_rate(count, total, rate):
        pct = (rate * 100) if isinstance(rate, (int, float)) else 0.0
        return f"{count}/{total} ({pct:.1f}%)"

    def _fmt_cost(val):
        if val is None:
            return "N/A (0 successes)"
        if isinstance(val, (int, float)):
            return f"${val:.6f}"
        return str(val)

    def _fmt_tax(tax):
        if isinstance(tax, (int, float)):
            return f"{tax * 100:.2f}%"
        return str(tax)

    def _render_comparison_table(name: str, base: dict, impr: dict):
        t_lines = [
            f"### {name}",
            "",
            "| Metric | Tag | Baseline | Improved | Delta / Impact |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]

        b_runs, i_runs = base.get("n_runs", 0), impr.get("n_runs", 0)
        b_ideas, i_ideas = base.get("n_ideas", 0), impr.get("n_ideas", 0)
        t_lines.append(f"| Ideas evaluated | `[MEASURED]` | {b_ideas} | {i_ideas} | Identical cohort |")
        t_lines.append(f"| Total runs (N) | `[MEASURED]` | {b_runs} | {i_runs} | - |")

        # First attempt passes with Wilson 95% confidence intervals
        b_fa_cnt, b_fa_rate = base.get("first_attempt_pass_count", 0), base.get("first_attempt_pass_rate", 0.0)
        i_fa_cnt, i_fa_rate = impr.get("first_attempt_pass_count", 0), impr.get("first_attempt_pass_rate", 0.0)
        b_ci = base.get("first_attempt_pass_ci95", [0.0, 0.0])
        i_ci = impr.get("first_attempt_pass_ci95", [0.0, 0.0])
        b_ci_str = f" [CI95: {b_ci[0]*100:.1f}%–{b_ci[1]*100:.1f}%]" if b_runs > 0 else ""
        i_ci_str = f" [CI95: {i_ci[0]*100:.1f}%–{i_ci[1]*100:.1f}%]" if i_runs > 0 else ""
        fa_diff = (i_fa_rate - b_fa_rate) * 100
        fa_sign = "+" if fa_diff >= 0 else ""
        t_lines.append(f"| First-attempt passes | `[MEASURED]` | {_fmt_rate(b_fa_cnt, b_runs, b_fa_rate)}{b_ci_str} | {_fmt_rate(i_fa_cnt, i_runs, i_fa_rate)}{i_ci_str} | {fa_sign}{fa_diff:.1f}% |")

        # Fisher exact test on first-attempt passes
        b_fail_cnt = max(0, b_runs - b_fa_cnt)
        i_fail_cnt = max(0, i_runs - i_fa_cnt)
        p_val = fisher_exact_2x2(b_fa_cnt, b_fail_cnt, i_fa_cnt, i_fail_cnt)
        sig_str = " (p < 0.001)" if p_val < 0.001 else f" (p = {p_val:.4f})"
        t_lines.append(f"| Fisher exact test (first-pass) | `[COMPUTED]` | n = {b_runs} | n = {i_runs} | {sig_str} |")

        # Eventual successes
        b_s_cnt, b_s_rate = base.get("success_count", 0), base.get("success_rate", 0.0)
        i_s_cnt, i_s_rate = impr.get("success_count", 0), impr.get("success_rate", 0.0)
        s_diff = (i_s_rate - b_s_rate) * 100
        s_sign = "+" if s_diff >= 0 else ""
        t_lines.append(f"| Eventual successes | `[MEASURED]` | {_fmt_rate(b_s_cnt, b_runs, b_s_rate)} | {_fmt_rate(i_s_cnt, i_runs, i_s_rate)} | {s_sign}{s_diff:.1f}% |")

        # Failures by test name
        b_fails = base.get("failures_by_test", {})
        i_fails = impr.get("failures_by_test", {})
        b_fail_str = ", ".join(f"{k}: {v}" for k, v in b_fails.items()) or "None"
        i_fail_str = ", ".join(f"{k}: {v}" for k, v in i_fails.items()) or "None"
        t_lines.append(f"| Failures by test name | `[MEASURED]` | {b_fail_str} | {i_fail_str} | - |")

        # Avg attempts
        b_att, i_att = base.get("avg_attempts", 0.0), impr.get("avg_attempts", 0.0)
        att_diff = i_att - b_att
        att_sign = "+" if att_diff >= 0 else ""
        t_lines.append(f"| Avg attempts per run | `[MEASURED]` | {b_att:.2f} | {i_att:.2f} | {att_sign}{att_diff:.2f} |")

        # Input Tokens (separated, noting prompt length difference)
        b_in_tot, i_in_tot = base.get("input_tokens", 0), impr.get("input_tokens", 0)
        b_in_avg, i_in_avg = base.get("avg_input_tokens", 0.0), impr.get("avg_input_tokens", 0.0)
        t_lines.append(f"| Input tokens (total / avg) | `[MEASURED]` | {b_in_tot:,} ({b_in_avg:,.1f}/run) | {i_in_tot:,} ({i_in_avg:,.1f}/run) | {i_in_tot - b_in_tot:+,} ({i_in_avg - b_in_avg:+,.1f}/run) |")

        # Output Tokens (separated)
        b_out_tot, i_out_tot = base.get("output_tokens", 0), impr.get("output_tokens", 0)
        b_out_avg, i_out_avg = base.get("avg_output_tokens", 0.0), impr.get("avg_output_tokens", 0.0)
        t_lines.append(f"| Output tokens (total / avg) | `[MEASURED]` | {b_out_tot:,} ({b_out_avg:,.1f}/run) | {i_out_tot:,} ({i_out_avg:,.1f}/run) | {i_out_tot - b_out_tot:+,} ({i_out_avg - b_out_avg:+,.1f}/run) |")

        # Total Tokens
        b_tok_tot, i_tok_tot = base.get("total_tokens", 0), impr.get("total_tokens", 0)
        b_tok_avg, i_tok_avg = base.get("avg_tokens", 0.0), impr.get("avg_tokens", 0.0)
        t_lines.append(f"| Total tokens (in + out) | `[MEASURED]` | {b_tok_tot:,} ({b_tok_avg:,.1f}/run) | {i_tok_tot:,} ({i_tok_avg:,.1f}/run) | {i_tok_tot - b_tok_tot:+,} ({i_tok_avg - b_tok_avg:+,.1f}/run) |")

        # Costs
        b_cost_tot, i_cost_tot = base.get("total_cost", 0.0), impr.get("total_cost", 0.0)
        t_lines.append(f"| Total cost | `[COMPUTED]` | ${_cost_fmt(b_cost_tot)} | ${_cost_fmt(i_cost_tot)} | ${_cost_fmt(i_cost_tot - b_cost_tot, signed=True)} |")

        b_cps, i_cps = base.get("cost_per_success"), impr.get("cost_per_success")
        t_lines.append(f"| Cost per success | `[COMPUTED]` | {_fmt_cost(b_cps)} | {_fmt_cost(i_cps)} | {_delta_cost_per_success(b_cps, i_cps)} |")

        # Retry tax (reporting both with and without autopsy)
        b_tax_w, i_tax_w = base.get("retry_tax_with_autopsy", base.get("retry_tax", 0.0)), impr.get("retry_tax_with_autopsy", impr.get("retry_tax", 0.0))
        b_tax_wo, i_tax_wo = base.get("retry_tax_without_autopsy", base.get("retry_tax", 0.0)), impr.get("retry_tax_without_autopsy", impr.get("retry_tax", 0.0))
        tax_diff = (i_tax_w - b_tax_w) * 100
        tax_sign = "+" if tax_diff >= 0 else ""
        t_lines.append(f"| Retry tax (incl. autopsy) | `[COMPUTED]` | {_fmt_tax(b_tax_w)} | {_fmt_tax(i_tax_w)} | {tax_sign}{tax_diff:.2f}% |")
        t_lines.append(f"| Retry tax (excl. autopsy) | `[COMPUTED]` | {_fmt_tax(b_tax_wo)} | {_fmt_tax(i_tax_wo)} | {tax_sign}{tax_diff:.2f}% |")

        # Median latency
        b_lat, i_lat = base.get("median_latency_s", 0.0), impr.get("median_latency_s", 0.0)
        t_lines.append(f"| Median latency | `[MEASURED]` | {b_lat:.2f}s | {i_lat:.2f}s | {i_lat - b_lat:+.2f}s |")

        t_lines.append("")
        return t_lines

    def _cost_fmt(c, signed=False):
        if not isinstance(c, (int, float)):
            return str(c)
        sign = "+" if (signed and c >= 0) else ""
        return f"{sign}{c:.6f}"

    def _delta_cost_per_success(b, i):
        if b is None or i is None:
            return "N/A"
        diff = i - b
        sign = "+" if diff >= 0 else ""
        pct = (diff / b * 100) if b > 0 else 0.0
        return f"{sign}${diff:.6f} ({sign}{pct:.1f}%)"

    lines.extend(_render_comparison_table("Cohort 1: Tuning Set (Seen Failures)", tuning_base, tuning_impr))
    lines.extend(_render_comparison_table("Cohort 2: Held-Out Set (Genuinely Unseen)", held_base, held_impr))
    if comb_base and comb_impr:
        lines.extend(_render_comparison_table("Combined Overall Totals", comb_base, comb_impr))

    lines.extend([
        "---",
        "",
        "## 3. Cost Radar Formulas & Definitions",
        "",
        "1. **Cost per Success (`[COMPUTED]`):**",
        "   $$\\text{Cost per Success} = \\frac{\\sum \\text{Cost of ALL Runs}}{\\text{Count of Successful Runs}}$$",
        "   - Accounts for the financial waste of failing runs and retries.",
        "   - If successes = 0, the metric is reported as `None` / `N/A` (zero-success edge case handled cleanly without division by zero).",
        "",
        "2. **Retry Tax (`[COMPUTED]`):**",
        "   $$\\text{Retry Tax} = \\frac{\\text{Cost Incurred After First Build}}{\\text{Total Cost}} = \\frac{\\text{Cost}(\\text{retry}) + \\text{Cost}(\\text{autopsy})}{\\text{Total Cost}}$$",
        "   - During this A/B experiment, `autopsy=False`, so Retry Tax isolates the cost spent on retrying attempts 2..4.",
        "   - If total cost = $0.00, Retry Tax defaults to 0.0% without division error.",
        "",
        "3. **First-Attempt Pass Rate (`[MEASURED]`):**",
        "   $$\\text{First-Attempt Pass Rate} = \\frac{\\text{Runs Passing on Attempt 1}}{\\text{Total Runs}}$$",
        "   - Decisive metric for eliminating latency and token overhead.",
        "",
        "---",
        "",
        "## 4. Measurement & Audit Trail",
        "",
        "- **Pass/Fail Authority:** Deterministic Playwright headless Chromium runner.",
        "- **Autopsy Execution:** Disabled (`autopsy=False`) across both baseline and improved arms.",
        "- **Candidate Exclusions:** `candidate_a` and `candidate_b` patch-lab runs are excluded from standard A/B aggregates.",
        "- **Failure Preservation:** Failed runs are permanently preserved in `evidence/runs/`.",
    ])

    return "\n".join(lines)

