"""Tests for Stage 2c A/B evaluation, arm prompt integrity, and Cost Radar metrics."""
import hashlib
import json
from pathlib import Path

import pytest

import config
from agent import loop, prompts
from agent.mock_llm import MockLLM
from evidence import metrics
from experiments import ab, arms
from experiments.ideas import HELD_OUT, TUNING


def test_idea_cohort_isolation():
    """Tuning and held-out idea sets must be mutually exclusive with 5 ideas each."""
    assert len(TUNING) == 5
    assert len(HELD_OUT) == 5
    intersection = set(TUNING).intersection(set(HELD_OUT))
    assert len(intersection) == 0, f"Leakage detected between cohorts: {intersection}"


def test_baseline_prompt_is_unchanged_v1():
    """Baseline arm must use unchanged BUILDER_SYSTEM_V1 without patches or edge cases."""
    baseline_sys = loop.builder_system("baseline", None)
    assert baseline_sys == prompts.BUILDER_SYSTEM_V1
    assert "edge cases" not in baseline_sys


def test_improved_prompt_adds_frozen_candidate_b_patch():
    """Improved arm must add the frozen Candidate B patch from evidence/patches/winner.txt."""
    repo_winner_txt = config.ROOT / "evidence" / "patches" / "winner.txt"
    assert repo_winner_txt.exists(), f"{repo_winner_txt} must exist in repository"
    winner_text = repo_winner_txt.read_text(encoding="utf-8").strip()
    assert "Before performing any calculation" in winner_text

    # Ensure tmp PATCH_DIR has the winner patch so load_winner_patch finds it under test isolation
    (config.PATCH_DIR / "winner.txt").write_text(winner_text + "\n", encoding="utf-8")
    winner_patch = loop.load_winner_patch()
    assert winner_patch == winner_text

    # Verify that improved builder prompt contains V1 and the frozen patch
    improved_sys = loop.builder_system("improved", winner_patch)
    assert prompts.BUILDER_SYSTEM_V1 in improved_sys
    assert winner_patch in improved_sys

    # Verify no held-out idea keywords leaked into the frozen patch
    lower_patch = winner_patch.lower()
    for forbidden in ["coffee", "brunch", "festival", "salon", "tour guide"]:
        assert forbidden not in lower_patch, f"Held-out leakage found in patch: {forbidden}"


def test_zero_success_edge_case_handling():
    """Aggregation must handle zero-success runs cleanly without ZeroDivisionError."""
    failed_runs = [
        {
            "run_id": "fail-1",
            "idea": TUNING[0],
            "mode": "baseline",
            "success": False,
            "attempts": 4,
            "first_attempt_passed": False,
            "tokens": 4000,
            "cost_usd": 0.04,
            "cost_by_stage": {"plan": 0.005, "build": 0.015, "retry": 0.02},
            "latency_s": 25.0,
        },
        {
            "run_id": "fail-2",
            "idea": TUNING[1],
            "mode": "baseline",
            "success": False,
            "attempts": 4,
            "first_attempt_passed": False,
            "tokens": 4500,
            "cost_usd": 0.045,
            "cost_by_stage": {"plan": 0.005, "build": 0.015, "retry": 0.025},
            "latency_s": 28.0,
        },
    ]

    agg = metrics.aggregate(failed_runs)
    assert agg["n_runs"] == 2
    assert agg["n_ideas"] == 2
    assert agg["success_count"] == 0
    assert agg["success_rate"] == 0.0
    assert agg["cost_per_success"] is None  # Must NOT divide by zero
    assert agg["tokens_per_success"] is None
    assert agg["total_cost"] == 0.085
    assert agg["retry_tax"] == round((0.02 + 0.025) / 0.085, 4)

    # Cost radar rendering must also handle None gracefully
    radar_md = metrics.render_cost_radar({
        "experiment": {
            "tuning": {"baseline": agg, "improved": agg},
            "held_out": {"baseline": agg, "improved": agg},
            "combined": {"baseline": agg, "improved": agg},
        },
        "meta": {"model": "test-model", "temperature": 0.2, "pricing_date": "2026-10-11"},
    })
    assert "N/A (0 successes)" in radar_md


def test_candidate_runs_excluded_from_ab_metrics(tmp_path):
    """Candidate A/B patch-lab runs must be strictly excluded from final A/B metrics."""
    # Create candidate run
    c_dir = tmp_path / "cand-run"
    c_dir.mkdir()
    (c_dir / "result.json").write_text(json.dumps({
        "run_id": "cand-run",
        "mode": "candidate_b",
        "idea": TUNING[0],
        "success": True,
        "first_attempt_passed": True,
        "attempts": 1,
        "cost_usd": 0.008,
    }), encoding="utf-8")

    # Create baseline run
    b_dir = tmp_path / "base-run"
    b_dir.mkdir()
    (b_dir / "result.json").write_text(json.dumps({
        "run_id": "base-run",
        "mode": "baseline",
        "idea": TUNING[0],
        "success": True,
        "first_attempt_passed": False,
        "attempts": 2,
        "cost_usd": 0.015,
    }), encoding="utf-8")

    valid, ex = metrics.load_runs(runs_dir=tmp_path, include_mock=True, cutoff=None, include_candidates=False)
    assert len(valid) == 1
    assert valid[0]["mode"] == "baseline"
    assert ex["by_reason"]["candidate"] == 1


def test_prompt_sha256_provenance():
    """Verify SHA-256 hashes for BUILDER_SYSTEM_V1, Improved Prompt (V1 + winner.txt), and RETRY_USER."""
    v1_text = prompts.BUILDER_SYSTEM_V1
    v1_hash = hashlib.sha256(v1_text.encode("utf-8")).hexdigest()
    assert len(v1_hash) == 64

    retry_text = prompts.RETRY_USER
    retry_hash = hashlib.sha256(retry_text.encode("utf-8")).hexdigest()
    assert len(retry_hash) == 64

    repo_winner = config.ROOT / "evidence" / "patches" / "winner.txt"
    winner_patch = repo_winner.read_text(encoding="utf-8").strip() if repo_winner.exists() else prompts.DEFAULT_V2_PATCH
    impr_text = f"{prompts.BUILDER_SYSTEM_V1}\n\n{winner_patch}"
    impr_hash = hashlib.sha256(impr_text.encode("utf-8")).hexdigest()
    assert len(impr_hash) == 64
    assert impr_hash != v1_hash
    assert len(impr_text) > len(v1_text)


def test_wilson_interval_and_fisher_exact_pure_python():
    """Verify statistical functions: Wilson 95% interval and two-tailed Fisher's exact test on exact known values.
    
    Target tests:
    - 2/10 vs 8/10 two-sided p about 0.0230
    - 0/10 vs 10/10 about 0.00001
    - 18/20 vs 19/20 equals 1.0
    - Wilson 95% for 8/10 is about (0.49, 0.94)
    """
    # 1. 2/10 vs 8/10 two-sided p about 0.0230
    p_2_8 = metrics.fisher_exact_2x2(2, 8, 8, 2)
    assert round(p_2_8, 4) == 0.0230

    # 2. 0/10 vs 10/10 about 0.00001 (1.1e-05)
    p_0_10 = metrics.fisher_exact_2x2(0, 10, 10, 0)
    assert 0.000010 <= p_0_10 <= 0.000012

    # 3. 18/20 vs 19/20 equals 1.0
    p_18_19 = metrics.fisher_exact_2x2(18, 2, 19, 1)
    assert p_18_19 == 1.0

    # 4. Wilson 95% for 8/10 is about (0.49, 0.94)
    ci_8_10 = metrics.wilson_score_interval(8, 10)
    assert round(ci_8_10[0], 2) == 0.49
    assert round(ci_8_10[1], 2) == 0.94

    # Baseline edge cases
    assert metrics.fisher_exact_2x2(10, 10, 10, 10) == 1.0
    ci_zero = metrics.wilson_score_interval(0, 20)
    assert ci_zero[0] == 0.0
    assert 0.16 <= ci_zero[1] <= 0.18


@pytest.mark.asyncio
async def test_ab_experiment_runner_mock(tmp_path, monkeypatch):
    """Run full A/B pipeline with MockLLM and verify outputs, hashes, interleaved schedule, and README."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    metrics_path = tmp_path / "evidence" / "metrics.json"
    radar_path = tmp_path / "evidence" / "cost_radar.md"
    readme_path = tmp_path / "evidence" / "ab" / "README.md"

    # Use 2 tuning and 2 held-out ideas for fast test execution
    test_tuning = TUNING[:2]
    test_held_out = HELD_OUT[:2]
    monkeypatch.setattr(ab, "TUNING", test_tuning)
    monkeypatch.setattr(ab, "HELD_OUT", test_held_out)

    results = await ab.run_ab_experiment(
        repeats=1,
        seed=42,
        llm=MockLLM(),
        runs_dir=runs_dir,
        metrics_path=metrics_path,
        cost_radar_path=radar_path,
        readme_path=readme_path,
        sleep_s=0.0,
    )

    assert metrics_path.exists()
    assert radar_path.exists()
    assert readme_path.exists()

    readme_content = readme_path.read_text(encoding="utf-8")
    assert "python -m experiments.ab" in readme_content
    assert "BUILDER_SYSTEM_V1" in readme_content
    assert "Cell: TUNING / BASELINE" in readme_content
    assert "Cell: HELD_OUT / IMPROVED" in readme_content
    assert "Statistical Independence Caveat" in readme_content

    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert "experiment" in data
    assert "tuning" in data["experiment"]
    assert "held_out" in data["experiment"]
    assert "combined" in data["experiment"]
    assert "cell_run_ids" in data
    assert "fisher_exact_p_values" in data

    # Check metadata and hashes
    meta = data["meta"]
    assert meta["seed"] == 42
    assert meta["interleaved"] is True
    assert meta["autopsy_enabled"] is False
    assert len(meta["builder_system_v1_sha256"]) == 64
    assert len(meta["builder_system_improved_sha256"]) == 64
    assert len(meta["retry_user_sha256"]) == 64
    assert "git_commit_hash" in meta
    assert len(meta["git_commit_hash"]) > 0

    for set_name in ("tuning", "held_out", "combined"):
        for mode in ("baseline", "improved"):
            cell = data["experiment"][set_name][mode]
            assert "n_runs" in cell
            assert "success_count" in cell
            assert "first_attempt_pass_count" in cell
            assert "first_attempt_pass_ci95" in cell
            assert "input_tokens" in cell
            assert "output_tokens" in cell
            assert "retry_tax_with_autopsy" in cell
            assert "retry_tax_without_autopsy" in cell
            assert cell["retry_tax_with_autopsy"] == cell["retry_tax_without_autopsy"]
            assert cell["n_runs"] == (4 if set_name == "combined" else 2)

    # Verify no autopsy ran (autopsy=False during experiment)
    for p in runs_dir.glob("*/autopsy.json"):
        pytest.fail(f"Autopsy file found in experiment run: {p}")


@pytest.mark.asyncio
async def test_ab_resume_skips_completed_runs(tmp_path, monkeypatch):
    """Verify that rerun after crash uses existing checkpoint and skips completed runs."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    metrics_path = tmp_path / "evidence" / "metrics.json"
    radar_path = tmp_path / "evidence" / "cost_radar.md"
    readme_path = tmp_path / "evidence" / "ab" / "README.md"
    progress_path = tmp_path / "evidence" / "ab" / "progress.json"

    test_tuning = TUNING[:1]
    test_held_out = HELD_OUT[:1]
    monkeypatch.setattr(ab, "TUNING", test_tuning)
    monkeypatch.setattr(ab, "HELD_OUT", test_held_out)

    # First run: 1 repeat (4 total runs: tuning base, tuning impr, held-out base, held-out impr)
    res1 = await ab.run_ab_experiment(
        repeats=1,
        seed=42,
        llm=MockLLM(),
        runs_dir=runs_dir,
        metrics_path=metrics_path,
        cost_radar_path=radar_path,
        readme_path=readme_path,
        progress_path=progress_path,
        resume=True,
        sleep_s=0.0,
    )
    first_run_ids = res1["run_ids"]
    assert len(first_run_ids) == 4
    assert progress_path.exists()

    # Second run with resume=True: should skip all 4 runs and reuse identical run_ids
    res2 = await ab.run_ab_experiment(
        repeats=1,
        seed=42,
        llm=MockLLM(),
        runs_dir=runs_dir,
        metrics_path=metrics_path,
        cost_radar_path=radar_path,
        readme_path=readme_path,
        progress_path=progress_path,
        resume=True,
        sleep_s=0.0,
    )
    assert res2["run_ids"] == first_run_ids
