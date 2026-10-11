import json
from pathlib import Path

import pytest

from evidence import metrics
from experiments.ideas import HELD_OUT, TUNING


def test_classify_idea():
    assert metrics.classify_idea(TUNING[0]) == "tuning"
    assert metrics.classify_idea(HELD_OUT[0]) == "held_out"
    assert metrics.classify_idea("Some random idea") == "other"
    assert metrics.classify_idea(None) == "other"


def test_is_pre_stage_1e():
    assert metrics.is_pre_stage_1e("20261011-035932-b372") is True
    assert metrics.is_pre_stage_1e("20261011-043459-0000") is True
    assert metrics.is_pre_stage_1e("20261011-043500-0000") is False
    assert metrics.is_pre_stage_1e("20261011-043734-40b9") is False


def test_load_runs_exclusions(tmp_path):
    # Pre-1e run
    d1 = tmp_path / "20261011-035000-aaaa"
    d1.mkdir()
    (d1 / "result.json").write_text(json.dumps({"run_id": "20261011-035000-aaaa", "mock": False, "cost_usd": 0.01}), encoding="utf-8")

    # Mock run
    d2 = tmp_path / "20261011-044000-bbbb"
    d2.mkdir()
    (d2 / "result.json").write_text(json.dumps({"run_id": "20261011-044000-bbbb", "mock": True, "cost_usd": 0.01}), encoding="utf-8")

    # Unpriced run
    d3 = tmp_path / "20261011-044000-cccc"
    d3.mkdir()
    (d3 / "result.json").write_text(json.dumps({"run_id": "20261011-044000-cccc", "mock": False, "cost_usd": "UNPRICED", "cost_tag": "UNPRICED"}), encoding="utf-8")

    # Valid post-1e run
    d4 = tmp_path / "20261011-044000-dddd"
    d4.mkdir()
    (d4 / "result.json").write_text(json.dumps({
        "run_id": "20261011-044000-dddd", "mock": False, "mode": "baseline",
        "success": True, "first_attempt_passed": False, "attempts": 2, "tokens": 5000,
        "cost_usd": 0.015, "cost_by_stage": {"plan": 0.001, "build": 0.005, "retry": 0.007, "autopsy": 0.002},
        "latency_s": 10.0,
    }), encoding="utf-8")

    valid, ex = metrics.load_runs(runs_dir=tmp_path)
    assert len(valid) == 1
    assert valid[0]["run_id"] == "20261011-044000-dddd"
    assert ex["total_scanned"] == 4
    assert ex["total_excluded"] == 3
    assert ex["by_reason"]["pre_stage_1e"] == 1
    assert ex["by_reason"]["mock"] == 1
    assert ex["by_reason"]["unpriced"] == 1


def test_aggregate_empty_records():
    res = metrics.aggregate([])
    assert res["n_runs"] == 0
    assert res["total_cost"] == 0.0
    assert res["cost_per_success"] is None
    assert res["retry_tax"] == 0.0


def test_aggregate_never_sums_strings_or_crashes():
    records = [
        {
            "run_id": "r1", "success": True, "first_attempt_passed": True,
            "attempts": 1, "tokens": 1000, "cost_usd": 0.01,
            "cost_by_stage": {"build": 0.01}, "latency_s": 5.0,
        },
        {
            "run_id": "r2", "success": True, "first_attempt_passed": False,
            "attempts": 2, "tokens": 2000, "cost_usd": "CORRUPT_STRING",
            "cost_by_stage": {"build": 0.01, "retry": "STRING_STAGE"}, "latency_s": 8.0,
        },
    ]
    res = metrics.aggregate(records)
    assert res["n_runs"] == 2
    assert res["success_count"] == 2
    assert res["total_cost"] == 0.01  # String cost ignored, never crashes


def test_aggregate_retry_tax_includes_autopsy():
    records = [
        {
            "run_id": "r1", "success": True, "first_attempt_passed": False,
            "attempts": 2, "tokens": 3000, "cost_usd": 0.02,
            "cost_by_stage": {"plan": 0.002, "build": 0.008, "autopsy": 0.002, "retry": 0.008},
            "latency_s": 12.0,
        }
    ]
    res = metrics.aggregate(records)
    # retry_tax = (retry 0.008 + autopsy 0.002) / total 0.02 = 0.50 (50%)
    assert res["retry_tax"] == 0.5
    assert res["cost_per_success"] == 0.02


def test_compute_metrics_and_report_runs(tmp_path):
    d = tmp_path / "20261011-044000-xxxx"
    d.mkdir()
    (d / "result.json").write_text(json.dumps({
        "run_id": "20261011-044000-xxxx", "mock": False, "mode": "baseline",
        "idea": TUNING[0], "success": True, "first_attempt_passed": True,
        "attempts": 1, "tokens": 2000, "cost_usd": 0.005,
        "cost_by_stage": {"plan": 0.001, "build": 0.004}, "latency_s": 4.5,
    }), encoding="utf-8")

    from experiments.report import generate_report
    rep = generate_report(runs_dir=tmp_path)
    assert "POCKET STARTUP: POST-STAGE 1e BASELINE RUNS REPORT" in rep
    assert "20261011-044000-xxxx" in rep
    assert "[MEASURED]" in rep
    assert "[COMPUTED]" in rep
