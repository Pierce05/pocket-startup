"""Unit tests for verdict engine, founder profiles, ledger, and CFO bridge (Stage 3)."""
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

import config
from cfo import bridge
import verdict

REAL_METRICS_PATH = config.ROOT / "evidence" / "metrics.json"
REAL_CFO_INPUT_PATH = config.ROOT / "evidence" / "cfo" / "cfo_input.md"


@pytest.fixture
def assumptions():
    return config.load_assumptions(config.ROOT / "assumptions.yaml")


@pytest.fixture
def headline_improved_arm():
    with open(REAL_METRICS_PATH, encoding="utf-8") as f:
        metrics = json.load(f)
    # Also ensure config.METRICS_PATH in tmp_evidence has a copy if needed
    if not config.METRICS_PATH.exists():
        shutil.copyfile(REAL_METRICS_PATH, config.METRICS_PATH)
    return metrics["experiment"]["combined"]["improved"]


@pytest.fixture
def founder_a():
    return verdict.load_founder_profile(config.ROOT / "founder_a.yaml")


@pytest.fixture
def founder_b():
    return verdict.load_founder_profile(config.ROOT / "founder_b.yaml")


# 1. Determinism: Same inputs give the same verdict
def test_same_inputs_give_same_verdict(headline_improved_arm, assumptions, founder_a):
    v1 = verdict.compute(headline_improved_arm, assumptions, founder_a)
    v2 = verdict.compute(headline_improved_arm, assumptions, founder_a)
    assert v1 == v2
    assert v1["verdict"] == v2["verdict"]
    assert v1["verdict"] == "BUILD"
    assert v1["reasons"] == v2["reasons"]
    assert v1["cheapest_next_experiment"] == v2["cheapest_next_experiment"]


# 2. Profiles give different verdicts: founder_a vs founder_b
def test_two_profiles_give_different_verdicts(headline_improved_arm, assumptions, founder_a, founder_b):
    va = verdict.compute(headline_improved_arm, assumptions, founder_a)
    vb = verdict.compute(headline_improved_arm, assumptions, founder_b)
    assert va["verdict"] != vb["verdict"]
    assert va["verdict"] == "BUILD"
    assert vb["verdict"] == "PIVOT"
    assert any("Demand Cap" in r and "[USER-PROVIDED]" in r for r in vb["reasons"])
    assert any("demand evidence is none [USER-PROVIDED]" in r for r in vb["reasons"])

    # Counterfactual: overriding demand_evidence to 'interviews' gives BUILD,
    # proving the demand cap is the only cause of the PIVOT verdict.
    counterfactual_b = dict(founder_b)
    counterfactual_b["demand_evidence"] = "interviews"
    v_cf = verdict.compute(headline_improved_arm, assumptions, counterfactual_b)
    assert v_cf["verdict"] == "BUILD"


# 3. Robustness: zero-success and missing values do not crash
def test_zero_successes_does_not_crash(assumptions, founder_a):
    zero_arm = {
        "n_runs": 10,
        "success_count": 0,
        "success_rate": 0.0,
        "first_attempt_pass_count": 0,
        "first_attempt_pass_rate": 0.0,
        "cost_per_success": None,
        "retry_tax": 0.0,
    }
    v = verdict.compute(zero_arm, assumptions, founder_a)
    assert v["verdict"] in ["KILL", "PIVOT"]
    assert isinstance(v["reasons"], list)
    assert len(v["reasons"]) > 0
    assert "cheapest_next_experiment" in v


def test_missing_values_and_empty_inputs_do_not_crash():
    v_empty = verdict.compute({}, {}, {})
    assert v_empty["verdict"] in ["BUILD", "PIVOT", "KILL"]
    assert isinstance(v_empty["reasons"], list)

    v_none = verdict.compute(None, None, None)
    assert v_none["verdict"] in ["BUILD", "PIVOT", "KILL"]
    assert isinstance(v_none["reasons"], list)


# 4. Bridge output: No unlabeled numbers
def test_no_unlabeled_number_in_bridge_output(assumptions, founder_a):
    with open(REAL_METRICS_PATH, encoding="utf-8") as f:
        metrics = json.load(f)
    text = bridge.render(metrics, assumptions, founder_a)

    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        if re.search(r"\d", line):
            assert any(tag in line for tag in ["[MEASURED]", "[COMPUTED]", "[USER-PROVIDED]", "[ASSUMED]"]), (
                f"Line {idx} contains an unlabeled number: {line!r}"
            )


def test_written_cfo_input_file_has_no_unlabeled_numbers(assumptions, founder_a):
    # Test file rendered in real repository
    assert REAL_CFO_INPUT_PATH.exists(), "evidence/cfo/cfo_input.md must exist"
    real_text = REAL_CFO_INPUT_PATH.read_text(encoding="utf-8")
    for idx, line in enumerate(real_text.splitlines(), start=1):
        if re.search(r"\d", line):
            assert any(tag in line for tag in ["[MEASURED]", "[COMPUTED]", "[USER-PROVIDED]", "[ASSUMED]"]), (
                f"Line {idx} in REAL cfo_input.md contains an unlabeled number: {line!r}"
            )

    # Test file written via bridge.write() into current config.CFO_DIR
    out_path = bridge.write(
        metrics_path=REAL_METRICS_PATH,
        assumptions_path=config.ROOT / "assumptions.yaml",
        founder_path=config.ROOT / "founder.yaml",
    )
    assert out_path.exists()
    out_text = out_path.read_text(encoding="utf-8")
    for idx, line in enumerate(out_text.splitlines(), start=1):
        if re.search(r"\d", line):
            assert any(tag in line for tag in ["[MEASURED]", "[COMPUTED]", "[USER-PROVIDED]", "[ASSUMED]"]), (
                f"Line {idx} in written cfo_input.md contains an unlabeled number: {line!r}"
            )


# 5. Layered verdict rules and demand cap
def test_demand_cap_caps_at_pivot_when_evidence_none(headline_improved_arm, assumptions, founder_a):
    profile_no_demand = dict(founder_a)
    profile_no_demand["demand_evidence"] = "none"
    v = verdict.compute(headline_improved_arm, assumptions, profile_no_demand)
    assert v["verdict"] == "PIVOT"
    assert any("demand evidence is none" in r.lower() for r in v["reasons"])
    assert v["cheapest_next_experiment"]["lever"] == "conduct customer interviews to validate demand before building"


def test_technical_layer_kill_on_low_success_rate(assumptions, founder_a):
    arm_low_sr = {
        "success_rate": 0.40,
        "first_attempt_pass_rate": 0.20,
        "cost_per_success": 0.01,
        "retry_tax": 0.10,
    }
    v = verdict.compute(arm_low_sr, assumptions, founder_a)
    assert v["verdict"] == "KILL"
    assert v["layer_verdicts"]["technical"] == "KILL"
    assert any("success rate 0.40 [MEASURED] is below kill threshold" in r for r in v["reasons"])


def test_economics_layer_kill_on_low_margin(headline_improved_arm, assumptions, founder_a):
    profile_low_price = dict(founder_a)
    profile_low_price["price_per_run_inr"] = 2.0  # cost is ~2.41 INR -> margin < 0
    v = verdict.compute(headline_improved_arm, assumptions, profile_low_price)
    assert v["verdict"] == "KILL"
    assert v["layer_verdicts"]["economics"] == "KILL"
    assert any("gross margin" in r and "[COMPUTED]" in r and "kill threshold" in r for r in v["reasons"])


def test_most_restrictive_layer_ordering(headline_improved_arm, assumptions, founder_a):
    # Kill on economics overrides build on technical
    p = dict(founder_a)
    p["price_per_run_inr"] = 1.0
    v = verdict.compute(headline_improved_arm, assumptions, p)
    assert v["verdict"] == "KILL"


# 6. Ledger verification
def test_ledger_json_structure_and_tags(tmp_path):
    ledger = verdict.generate_ledger(
        metrics_path=REAL_METRICS_PATH,
        assumptions_path=config.ROOT / "assumptions.yaml",
        founder_path=config.ROOT / "founder.yaml",
    )
    assert isinstance(ledger, dict)
    assert len(ledger) >= 25
    valid_tags = {"MEASURED", "COMPUTED", "USER-PROVIDED", "ASSUMED", "CONFIG"}
    for name, item in ledger.items():
        assert "value" in item, f"Missing 'value' in ledger item {name}"
        assert "tag" in item, f"Missing 'tag' in ledger item {name}"
        assert item["tag"] in valid_tags, f"Invalid tag {item['tag']} in ledger item {name}"
        assert "source" in item, f"Missing 'source' in ledger item {name}"

    # Verify model is taken from metrics.json
    assert ledger["model"]["value"] == "gemini-3.5-flash-lite"

    # Verify model falls back to 'unknown' when not recorded in metrics.json
    empty_metrics = tmp_path / "empty_metrics.json"
    empty_metrics.write_text("{}", encoding="utf-8")
    ledger_empty = verdict.generate_ledger(
        metrics_path=empty_metrics,
        assumptions_path=config.ROOT / "assumptions.yaml",
        founder_path=config.ROOT / "founder.yaml",
    )
    assert ledger_empty["model"]["value"] == "unknown"


def test_cheapest_next_experiments_tags_and_currency(assumptions, founder_a):
    for key, item in verdict.CHEAPEST_NEXT_EXPERIMENTS.items():
        assert "[ASSUMED]" in item["estimated_cost"]

    # Test computed estimated_cost currency math consistency at usd_inr 85.0
    v = verdict.compute({"success_rate": 0.4, "cost_per_success": 0.01}, {"usd_inr": 85.0}, founder_a)
    assert v["cheapest_next_experiment"]["estimated_cost"] == "42.50 INR ($0.50 LLM API calls) [ASSUMED]"

    v_zero = verdict.compute({}, {"usd_inr": 85.0}, founder_a)
    assert v_zero["cheapest_next_experiment"]["estimated_cost"] == "12.75 INR ($0.15 LLM API calls) [ASSUMED]"

    # Test with custom usd_inr
    v_custom = verdict.compute({}, {"usd_inr": 90.0}, founder_a)
    assert v_custom["cheapest_next_experiment"]["estimated_cost"] == "13.50 INR ($0.15 LLM API calls) [ASSUMED]"


# 7. Founder schema validation
def test_founder_schema_validation():
    fa = verdict.load_founder_profile(config.ROOT / "founder_a.yaml")
    fb = verdict.load_founder_profile(config.ROOT / "founder_b.yaml")
    base = verdict.load_founder_profile(config.ROOT / "founder.yaml")
    for profile in [fa, fb, base]:
        verdict.validate_founder(profile)

    with pytest.raises(ValueError, match="missing required keys"):
        verdict.validate_founder({"target_user": "abc"})

    with pytest.raises(ValueError, match="Invalid demand_evidence"):
        bad_demand = dict(fa)
        bad_demand["demand_evidence"] = "unverified_rumor"
        verdict.validate_founder(bad_demand)


# 8. Bridge includes failures-by-test and README pool-style limitation
def test_cfo_bridge_includes_failures_and_limitation(assumptions, founder_a):
    with open(REAL_METRICS_PATH, encoding="utf-8") as f:
        metrics = json.load(f)
    text = bridge.render(metrics, assumptions, founder_a)
    assert "Failures by test" in text
    assert "split_basic failures" in text
    assert "fractional_people failures" in text
    assert "Known limitation on pool-style ideas" in text
    assert "SalonPool Tips" in text


# 9. CLI output verification
def test_verdict_cli_output(capsys):
    # Test founder A with default held-out cohort
    verdict.main(["--founder", "a"])
    captured_a = capsys.readouterr().out
    assert "Verdict: BUILD" in captured_a
    assert "Cohort fed to technical layer: improved arm, held_out cohort of evidence/metrics.json" in captured_a
    assert "conservative choice for ideas the patch never saw" in captured_a
    assert "Reasons:" in captured_a
    assert "[MEASURED]" in captured_a
    assert "[COMPUTED]" in captured_a
    assert "[USER-PROVIDED]" in captured_a
    assert "Cheapest Next Experiment:" in captured_a
    assert "Deploy MVP to initial cohort of 10 pilot users" in captured_a

    # Test founder B with default held-out cohort
    verdict.main(["--founder", "b"])
    captured_b = capsys.readouterr().out
    assert "Verdict: PIVOT" in captured_b
    assert "Cohort fed to technical layer: improved arm, held_out cohort of evidence/metrics.json" in captured_b
    assert "demand evidence is none [USER-PROVIDED]" in captured_b
    assert "Conduct 5 problem discovery interviews" in captured_b

    # Test cohort flag override
    verdict.main(["--founder", "a", "--cohort", "combined"])
    captured_comb = capsys.readouterr().out
    assert "Verdict: BUILD" in captured_comb
    assert "Cohort fed to technical layer: improved arm, combined cohort of evidence/metrics.json" in captured_comb

