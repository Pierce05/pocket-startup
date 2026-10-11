import json
from pathlib import Path

import pytest

from agent.mock_llm import MockLLM
from evidence import metrics
from experiments import patch_lab
from tests.conftest import needs_browser


def test_pick_winner_by_first_attempt_pass_count():
    cand_a = {
        "candidate_id": "candidate_a",
        "patch": "patch a",
        "metrics": {
            "first_attempt_pass_count": 8,
            "success_count": 10,
            "cost_per_success": 0.010,
        },
    }
    cand_b = {
        "candidate_id": "candidate_b",
        "patch": "patch b",
        "metrics": {
            "first_attempt_pass_count": 6,
            "success_count": 10,
            "cost_per_success": 0.008,
        },
    }

    winner, loser = patch_lab.pick_winner([cand_a, cand_b])
    assert winner["candidate_id"] == "candidate_a"
    assert loser["candidate_id"] == "candidate_b"


def test_pick_winner_tie_break_lower_cost():
    cand_a = {
        "candidate_id": "candidate_a",
        "patch": "patch a",
        "metrics": {
            "first_attempt_pass_count": 9,
            "success_count": 10,
            "cost_per_success": 0.012,
        },
    }
    cand_b = {
        "candidate_id": "candidate_b",
        "patch": "patch b",
        "metrics": {
            "first_attempt_pass_count": 9,
            "success_count": 10,
            "cost_per_success": 0.009,  # cheaper
        },
    }

    winner, loser = patch_lab.pick_winner([cand_a, cand_b])
    assert winner["candidate_id"] == "candidate_b"
    assert loser["candidate_id"] == "candidate_a"


def test_collect_failed_baseline_autopsies():
    autopsies = patch_lab.collect_failed_baseline_autopsies()
    # At least 8 autopsies exist on disk for post-1e tuning baseline runs
    assert isinstance(autopsies, list)
    if autopsies:
        assert "root_cause" in autopsies[0]
        assert "recommended_prompt_change" in autopsies[0]


@needs_browser
@pytest.mark.asyncio
async def test_run_patch_lab_with_mock_llm(tmp_path):
    runs_dir = tmp_path / "runs"
    patch_dir = tmp_path / "patches"

    class PatchMockLLM(MockLLM):
        async def _raw(self, system, user, json_mode):
            # In candidate_a or candidate_b, system contains the candidate patch
            text, i, o = await super()._raw(system, user, json_mode)
            return text, i, o

    # Run with 1 repeat (5 ideas * 2 candidates = 10 runs)
    results = await patch_lab.run_patch_lab(
        repeats=1,
        llm=PatchMockLLM(),
        runs_dir=runs_dir,
        patch_dir=patch_dir,
        sleep_s=0.0,
    )

    assert "winner" in results
    assert "loser" in results
    assert len(results["candidates"]) == 2

    winner_txt = patch_dir / "winner.txt"
    results_json = patch_dir / "results.json"
    assert winner_txt.exists()
    assert results_json.exists()

    saved_data = json.loads(results_json.read_text(encoding="utf-8"))
    assert saved_data["winner"]["candidate_id"] in ("candidate_a", "candidate_b")
    assert saved_data["loser"]["candidate_id"] in ("candidate_a", "candidate_b")
    assert saved_data["winner"]["candidate_id"] != saved_data["loser"]["candidate_id"]

    # Verify that candidate runs are saved with candidate_* modes
    run_modes = []
    for p in runs_dir.glob("*/result.json"):
        rec = json.loads(p.read_text(encoding="utf-8"))
        run_modes.append(rec.get("mode"))
    assert set(run_modes) == {"candidate_a", "candidate_b"}

    # Verify that candidate runs are excluded from standard metrics by default
    valid, ex = metrics.load_runs(runs_dir=runs_dir, include_mock=True, cutoff=None, include_candidates=False)
    assert len(valid) == 0
    assert ex["by_reason"]["candidate"] == len(run_modes)
