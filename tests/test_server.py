"""Unit and integration tests for FastAPI server (server/app.py).

Uses FastAPI TestClient with MockLLM.
Tests write strictly to tmp_path.
Covers every endpoint, replay, and path traversal protection.
"""
import json
from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

import config
from server.app import app, hub

REAL_METRICS_PATH = config.ROOT / "evidence" / "metrics.json"
REAL_WINNER_PATH = config.ROOT / "evidence" / "patches" / "winner.txt"
REAL_PROMPTS_PATH = config.ROOT / "agent" / "prompts.py"
REAL_ASSUMPTIONS_PATH = config.ROOT / "assumptions.yaml"
REAL_FOUNDER_A_PATH = config.ROOT / "founder_a.yaml"
REAL_FOUNDER_B_PATH = config.ROOT / "founder_b.yaml"
REAL_FOUNDER_BASE_PATH = config.ROOT / "founder.yaml"
REAL_PLAN_NUMBERS_PATH = config.ROOT / "evidence" / "cfo" / "plan_numbers.json"
REAL_PLAN_SUMMARY_PATH = config.ROOT / "evidence" / "cfo" / "plan_summary.md"


@pytest.fixture(autouse=True)
def setup_tmp_environment(tmp_path, monkeypatch):
    """Isolate server file operations strictly inside tmp_path."""
    hub.clear()

    # Directories
    evidence_dir = tmp_path / "evidence"
    runs_dir = evidence_dir / "runs"
    cfo_dir = evidence_dir / "cfo"
    patches_dir = evidence_dir / "patches"
    ui_dir = tmp_path / "ui"
    agent_dir = tmp_path / "agent"

    for d in [evidence_dir, runs_dir, cfo_dir, patches_dir, ui_dir, agent_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Copy / mock needed reference files to tmp_path
    metrics_path = evidence_dir / "metrics.json"
    if REAL_METRICS_PATH.exists():
        shutil.copyfile(REAL_METRICS_PATH, metrics_path)
    else:
        metrics_path.write_text("{}", encoding="utf-8")

    winner_path = patches_dir / "winner.txt"
    if REAL_WINNER_PATH.exists():
        shutil.copyfile(REAL_WINNER_PATH, winner_path)
    else:
        winner_path.write_text("Dummy winner patch", encoding="utf-8")

    prompts_path = agent_dir / "prompts.py"
    if REAL_PROMPTS_PATH.exists():
        shutil.copyfile(REAL_PROMPTS_PATH, prompts_path)

    assumptions_path = tmp_path / "assumptions.yaml"
    if REAL_ASSUMPTIONS_PATH.exists():
        shutil.copyfile(REAL_ASSUMPTIONS_PATH, assumptions_path)

    for src, name in [
        (REAL_FOUNDER_A_PATH, "founder_a.yaml"),
        (REAL_FOUNDER_B_PATH, "founder_b.yaml"),
        (REAL_FOUNDER_BASE_PATH, "founder.yaml"),
    ]:
        if src.exists():
            shutil.copyfile(src, tmp_path / name)

    real_ui_dir = config.ROOT / "ui"
    if real_ui_dir.exists():
        for f in real_ui_dir.glob("*"):
            if f.is_file():
                shutil.copyfile(f, ui_dir / f.name)

    real_ab_dir = config.ROOT / "evidence" / "ab"
    if real_ab_dir.exists():
        ab_dir = evidence_dir / "ab"
        ab_dir.mkdir(parents=True, exist_ok=True)
        for f in real_ab_dir.glob("*"):
            if f.is_file():
                shutil.copyfile(f, ab_dir / f.name)

    real_ledger = config.ROOT / "evidence" / "ledger.json"
    if real_ledger.exists():
        shutil.copyfile(real_ledger, evidence_dir / "ledger.json")

    # Real demo runs for replay tests
    for r_id in ["20261011-043610-3f24", "20261011-073159-a490"]:
        src_r = config.ROOT / "evidence" / "runs" / r_id
        if src_r.exists():
            dst_r = runs_dir / r_id
            dst_r.mkdir(parents=True, exist_ok=True)
            for rf in src_r.glob("*"):
                if rf.is_file():
                    shutil.copyfile(rf, dst_r / rf.name)

    # Monkeypatch config paths to tmp_path
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "EVIDENCE", evidence_dir)
    monkeypatch.setattr(config, "RUNS", runs_dir)
    monkeypatch.setattr(config, "CFO_DIR", cfo_dir)
    monkeypatch.setattr(config, "PATCH_DIR", patches_dir)
    monkeypatch.setattr(config, "METRICS_PATH", metrics_path)
    monkeypatch.setattr(config, "LEDGER_PATH", evidence_dir / "ledger.json")
    monkeypatch.setattr(config, "ASSUMPTIONS_PATH", assumptions_path)
    monkeypatch.setattr(config, "FOUNDER_PATH", tmp_path / "founder.yaml")
    monkeypatch.setattr(config, "POCKET_MOCK", True)

    yield

    hub.clear()



@pytest.fixture
def client():
    return TestClient(app)


# 1. Health
def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


# 2. Config & Security (No secrets exposed)
def test_config_endpoint_no_secrets(client):
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "mock" in data
    assert "model" in data
    assert "pricing_date" in data
    assert isinstance(data["has_api_key"], bool)
    assert isinstance(data["neatlogs"], bool)
    # Verify no raw API keys in response
    text = res.text
    assert "AIza" not in text
    assert "sk-" not in text


# 3. POST /api/runs (Validation and Mock Execution)
def test_post_runs_validation(client):
    # Empty idea
    r_empty = client.post("/api/runs", json={"idea": "   ", "mode": "baseline", "mock": True})
    assert r_empty.status_code == 400

    # Invalid mode
    r_mode = client.post("/api/runs", json={"idea": "Split bills", "mode": "invalid_mode", "mock": True})
    assert r_mode.status_code == 400


def test_post_runs_mock_execution(client):
    res = client.post(
        "/api/runs",
        json={"idea": "Office coffee tip splitter", "mode": "baseline", "mock": True, "sync": True},
    )
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data
    run_id = data["run_id"]

    # Verify run record written to disk in tmp_path
    run_dir = config.RUNS / run_id
    assert run_dir.exists()
    result_p = run_dir / "result.json"
    assert result_p.exists()
    rec = json.loads(result_p.read_text(encoding="utf-8"))
    assert rec["run_id"] == run_id
    assert rec["mock"] is True
    assert "success" in rec
    assert (run_dir / "events.json").exists()


# 4. GET /api/runs (List recent runs)
def test_get_runs_list(client):
    # Create two dummy runs
    d1 = config.RUNS / "run-001"
    d1.mkdir(parents=True, exist_ok=True)
    (d1 / "result.json").write_text(json.dumps({
        "run_id": "run-001",
        "idea": "Idea 1",
        "mode": "baseline",
        "success": True,
        "attempts": 1,
        "first_attempt_passed": True,
        "cost_usd": 0.01,
        "mock": False,
        "approved": False,
    }), encoding="utf-8")

    d2 = config.RUNS / "run-002"
    d2.mkdir(parents=True, exist_ok=True)
    (d2 / "result.json").write_text(json.dumps({
        "run_id": "run-002",
        "idea": "Idea 2",
        "mode": "improved",
        "success": False,
        "attempts": 4,
        "first_attempt_passed": False,
        "cost_usd": 0.04,
        "mock": True,
        "approved": False,
    }), encoding="utf-8")

    res = client.get("/api/runs")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    ids = [item["run_id"] for item in items]
    assert "run-001" in ids
    assert "run-002" in ids
    run2 = next(i for i in items if i["run_id"] == "run-002")
    assert run2["mock"] is True
    assert run2["success"] is False


# 5. GET /api/runs/{id}
def test_get_run_detail(client):
    d = config.RUNS / "run-detail-test"
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text(json.dumps({
        "run_id": "run-detail-test",
        "idea": "Detail idea",
        "success": True,
    }), encoding="utf-8")

    res = client.get("/api/runs/run-detail-test")
    assert res.status_code == 200
    assert res.json()["run_id"] == "run-detail-test"

    # Nonexistent run
    r_404 = client.get("/api/runs/nonexistent-run")
    assert r_404.status_code == 404


# 6. GET /api/runs/{id}/events (SSE)
def test_get_run_events_sse(client):
    stream = hub.create("sse-test-run")
    # Pre-populate and finish stream
    import asyncio
    asyncio.run(stream.publish("run_started", {"idea": "test"}))
    asyncio.run(stream.publish("run_finished", {"success": True}))
    asyncio.run(stream.finish())

    with client.stream("GET", "/api/runs/sse-test-run/events") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())
        text = "\n".join(lines)
        assert "run_started" in text
        assert "run_finished" in text
        assert "event: end" in text

    # Nonexistent stream
    r_404 = client.get("/api/runs/nonexistent-stream/events")
    assert r_404.status_code == 404


# 7. POST /api/runs/{id}/approve
def test_approve_run_flow(client):
    # Failing run cannot be approved
    d_fail = config.RUNS / "run-fail"
    d_fail.mkdir(parents=True, exist_ok=True)
    (d_fail / "result.json").write_text(json.dumps({
        "run_id": "run-fail",
        "success": False,
        "approved": False,
    }), encoding="utf-8")

    r_fail = client.post("/api/runs/run-fail/approve")
    assert r_fail.status_code == 409

    # Passing run can be approved
    d_pass = config.RUNS / "run-pass"
    d_pass.mkdir(parents=True, exist_ok=True)
    (d_pass / "result.json").write_text(json.dumps({
        "run_id": "run-pass",
        "success": True,
        "approved": False,
    }), encoding="utf-8")

    r_pass = client.post("/api/runs/run-pass/approve")
    assert r_pass.status_code == 200
    assert r_pass.json()["approved"] is True
    assert r_pass.json()["status"] == "approved"

    # Verify updated on disk
    rec = json.loads((d_pass / "result.json").read_text(encoding="utf-8"))
    assert rec["approved"] is True


# 8. POST /api/runs/{id}/kill
def test_kill_run(client):
    from agent.rails import Rails
    stream = hub.create("run-kill-test")
    rails = Rails(0.5, 4, 60)
    stream.rails = rails

    res = client.post("/api/runs/run-kill-test/kill")
    assert res.status_code == 200
    assert res.json()["killed"] is True
    assert rails.killed is True

    # Killing nonexistent run
    r_404 = client.post("/api/runs/nonexistent-run/kill")
    assert r_404.status_code == 404


# 9. POST /api/replay/{id}
def test_replay_endpoint_and_events(client):
    d = config.RUNS / "replay-source"
    d.mkdir(parents=True, exist_ok=True)
    events = [
        {"type": "run_started", "data": {"idea": "replay idea"}, "t": 0.0},
        {"type": "check_passed", "data": {"test": "split_basic"}, "t": 0.05},
        {"type": "run_finished", "data": {"success": True}, "t": 0.1},
    ]
    (d / "events.json").write_text(json.dumps(events), encoding="utf-8")

    # Invalid speed
    r_bad_speed = client.post("/api/replay/replay-source?speed=3")
    assert r_bad_speed.status_code == 400

    # Nonexistent run
    r_404 = client.post("/api/replay/nonexistent-replay")
    assert r_404.status_code == 404

    # Synchronous replay for test
    res = client.post("/api/replay/replay-source?speed=4&sync=true")
    assert res.status_code == 200
    data = res.json()
    assert "replay_id" in data
    assert data["events"] == 3
    assert data["speed"] == 4.0

    replay_id = data["replay_id"]
    with client.stream("GET", f"/api/runs/{replay_id}/events") as response:
        assert response.status_code == 200
        text = "\n".join(response.iter_lines())
        assert "run_started" in text
        assert "check_passed" in text
        assert "run_finished" in text
        assert "event: end" in text


# 10. GET /api/metrics (Read-only)
def test_metrics_endpoint_read_only(client):
    m_before = config.METRICS_PATH.read_text(encoding="utf-8")
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "experiment" in data
    m_after = config.METRICS_PATH.read_text(encoding="utf-8")
    assert m_before == m_after, "GET /api/metrics must not modify metrics.json"


# 11. GET /api/verdict?founder=a|b
def test_verdict_endpoint_no_llm(client):
    # Founder A with held_out cohort gives BUILD
    ra = client.get("/api/verdict?founder=a&cohort=held_out")
    assert ra.status_code == 200
    data_a = ra.json()
    assert data_a["verdict"] == "BUILD"
    assert "layer_verdicts" in data_a
    assert "reasons" in data_a
    assert "cheapest_next_experiment" in data_a

    # Founder B with held_out cohort gives PIVOT (due to demand evidence none)
    rb = client.get("/api/verdict?founder=b&cohort=held_out")
    assert rb.status_code == 200
    data_b = rb.json()
    assert data_b["verdict"] == "PIVOT"
    assert any("demand evidence is none" in r.lower() for r in data_b["reasons"])


def test_post_founder_verdict_custom_profile(client):
    # Valid custom profile with demand_evidence interviews
    res = client.post("/api/founder/verdict", json={
        "target_user": "Freelancers",
        "demand_evidence": "interviews",
        "budget_inr": 400000,
        "price_per_run_inr": 60.0,
        "cohort": "held_out",
    })
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "BUILD"
    assert "layer_verdicts" in data

    # Custom profile with demand_evidence none caps verdict at PIVOT
    res_pivot = client.post("/api/verdict", json={
        "demand_evidence": "none",
        "cohort": "held_out",
    })
    assert res_pivot.status_code == 200
    assert res_pivot.json()["verdict"] == "PIVOT"

    # Invalid demand evidence returns 400
    res_bad = client.post("/api/founder/verdict", json={
        "demand_evidence": "unverified_survey",
    })
    assert res_bad.status_code == 400


# 12. GET /api/ledger
def test_ledger_endpoint(client):
    res = client.get("/api/ledger")
    assert res.status_code == 200
    ledger = res.json()
    assert isinstance(ledger, dict)
    assert "success_rate" in ledger
    assert "retry_tax" in ledger
    assert "tag" in ledger["success_rate"]


# 13. GET /api/evidence
def test_evidence_endpoint(client):
    res = client.get("/api/evidence")
    assert res.status_code == 200
    data = res.json()

    # (a) No duplicate keys at top level
    assert "cell_counts" not in data, "cell_counts is a duplicate of run_counts_per_cell"
    assert "trailers" not in data, "trailers is a duplicate of git_log_trailers"
    assert "reproduce" not in data, "reproduce is a duplicate of reproduce_commands"

    # (b) Exactly 7 claims with FOUND or MISSING status
    assert "claims" in data
    claim_names = [c["claim"] for c in data["claims"]]
    assert len(data["claims"]) == 7
    expected_claims = [
        "First-attempt lift",
        "Held-out result",
        "Cost per success",
        "Entire checkpoints",
        "neatlogs trace links",
        "cfo.ai plan files",
        "Verdict ledger",
    ]
    for exp_c in expected_claims:
        assert exp_c in claim_names, f"Expected claim {exp_c} missing from claims list"

    for claim in data["claims"]:
        assert claim["status"] in ("FOUND", "MISSING")
        assert "proof" in claim
        for p in claim["proof"]:
            assert p["status"] in ("FOUND", "MISSING")

    # (c) Specific claim wording checks
    # Held-out claim: leads with first-attempt passes (1/20 vs 16/20, with Fisher p) and states eventual success 15/20 vs 19/20: not statistically significant
    held_out_claim = next(c for c in data["claims"] if c["claim"] == "Held-out result")
    h_label = held_out_claim["proof"][0]["label"]
    assert "First-attempt passes: 1/20 vs 16/20" in h_label
    assert "2e-06" in h_label or "p=" in h_label
    assert "eventual success 15/20 vs 19/20: not statistically significant" in h_label

    # Cost-per-success claim: names cohort (held-out) and shows combined ($0.016808 vs $0.006863)
    cps_claim = next(c for c in data["claims"] if c["claim"] == "Cost per success")
    cps_label = cps_claim["proof"][0]["label"]
    assert "Held-out:" in cps_label
    assert "Combined:" in cps_label
    assert "$0.016808" in cps_label
    assert "$0.006863" in cps_label

    # (d) Provenance & SHA-256 hashes
    assert data.get("metrics_sha_match") == "MATCH"
    assert "hashes" in data
    hashes = data["hashes"]
    assert "evidence/metrics.json" in hashes
    assert "evidence/ab/metrics.sha256" in hashes

    # Winner patch hash labelling: file bytes vs prompt text (stripped)
    assert "winner.txt (file bytes)" in hashes
    assert "winner.txt (prompt text (stripped))" in hashes
    assert hashes["winner.txt (file bytes)"] == "35fec47a8b8ef971239cb2df886d9a4bc874b2f1ffcbcaf26adc70306be809a9"
    assert hashes["winner.txt (prompt text (stripped))"] == "49156a531807280673be59af60163f3f8b5af05a470ab5262a4b74f510c8995c"
    assert "evidence/patches/winner.txt" not in hashes, "Duplicate winner patch hash entry must be removed"
    assert "winner.txt" not in hashes, "Ambiguous winner.txt hash entry replaced with labelled entries"
    assert "winner_patch_match" in hashes
    assert "MATCH" in hashes["winner_patch_match"]
    assert data.get("winner_patch_match") == hashes["winner_patch_match"]

    assert hashes["agent/prompts.py"] is not None
    assert hashes["BUILDER_SYSTEM_V1"] is not None
    assert hashes["RETRY_USER"] is not None

    # (e) Run counts per cell (20 runs each)
    assert "run_counts_per_cell" in data
    cell_counts = data["run_counts_per_cell"]
    assert cell_counts["tuning/baseline"] == 20
    assert cell_counts["tuning/improved"] == 20
    assert cell_counts["held_out/baseline"] == 20
    assert cell_counts["held_out/improved"] == 20

    # (f) Reproduce commands from README: single list, parsed cleanly one command per entry
    assert "reproduce_commands" in data
    assert isinstance(data["reproduce_commands"], list)
    for cmd in data["reproduce_commands"]:
        assert not cmd.startswith(">"), f"Command line must not have markdown quote prefix: {cmd}"
        assert "```" not in cmd, f"Command line must not contain markdown fences: {cmd}"
        assert "\n" not in cmd, f"Each command must be a single line, got multi-line: {cmd}"
    assert "python -m experiments.ab --repeats 4 --seed 42 --sleep 1.0" in data["reproduce_commands"]

    # (g) Limitations box (4 items)
    assert "limitations" in data
    assert len(data["limitations"]) == 4
    lim_text = " ".join(data["limitations"]).lower()
    assert "tip-pool" in lim_text
    assert "whole-number-people" in lim_text
    assert "same template" in lim_text
    assert "n is small" in lim_text

    # (h) Git log trailers
    assert "git_log_trailers" in data
    assert isinstance(data["git_log_trailers"], list)




# 14. GET /api/plan (Ready vs Pending)
def test_plan_endpoint(client):
    # Initially cfo_dir has no plan_numbers.json / plan_summary.md in clean tmp_path
    r_pending = client.get("/api/plan")
    assert r_pending.status_code == 200
    data_pending = r_pending.json()
    assert data_pending["status"] == "PENDING"
    assert data_pending["plan_numbers"] == "PENDING"
    assert data_pending["plan_summary"] == "PENDING"

    # Add plan_numbers.json and plan_summary.md
    if REAL_PLAN_NUMBERS_PATH.exists():
        shutil.copyfile(REAL_PLAN_NUMBERS_PATH, config.CFO_DIR / "plan_numbers.json")
    else:
        (config.CFO_DIR / "plan_numbers.json").write_text(json.dumps({"test_num": 1}), encoding="utf-8")

    if REAL_PLAN_SUMMARY_PATH.exists():
        shutil.copyfile(REAL_PLAN_SUMMARY_PATH, config.CFO_DIR / "plan_summary.md")
    else:
        (config.CFO_DIR / "plan_summary.md").write_text("# Plan Summary", encoding="utf-8")

    r_ready = client.get("/api/plan")
    assert r_ready.status_code == 200
    data_ready = r_ready.json()
    assert data_ready["status"] == "READY"
    assert isinstance(data_ready["plan_numbers"], dict)
    assert isinstance(data_ready["plan_summary"], str)


# 15. Built App & Trust
def test_built_app_and_trust_endpoints(client):
    d = config.RUNS / "run-built-app"
    d.mkdir(parents=True, exist_ok=True)
    html_content = "<!doctype html><html><body><h1>Tip Splitter App</h1></body></html>"
    (d / "index.html").write_text(html_content, encoding="utf-8")
    (d / "result.json").write_text(json.dumps({
        "run_id": "run-built-app",
        "approved": True,
        "rails_fired": [{"rail": "budget", "message": "cap reached"}],
    }), encoding="utf-8")

    r_app = client.get("/api/runs/run-built-app/app")
    assert r_app.status_code == 200
    assert "Tip Splitter App" in r_app.text
    assert "Content-Security-Policy" in r_app.headers

    r_trust = client.get("/api/trust/run-built-app")
    assert r_trust.status_code == 200
    trust_data = r_trust.json()
    assert trust_data["approved"] is True
    assert len(trust_data["rails"]) >= 5
    budget_rail = next(r for r in trust_data["rails"] if r["rail"] == "Budget cap")
    assert budget_rail["fired"] is True


# 16. Security: Path Traversal Protection & No Secret Exposure
def test_path_traversal_protection(client, tmp_path):
    # Create a secret .env file in tmp_path
    secret_env = tmp_path / ".env"
    secret_env.write_text("SUPER_SECRET_KEY=do_not_reveal_this\n", encoding="utf-8")

    # 1. UI path traversal
    for path in ["../.env", "../../.env", "..\\..\\.env", "....//.env"]:
        r = client.get(f"/ui/{path}")
        assert r.status_code in (400, 403, 404), f"Path traversal succeeded on /ui/{path}"
        assert "SUPER_SECRET_KEY" not in r.text

    # 2. Evidence path traversal
    for path in ["../.env", "../../.env", "..\\..\\.env", "..//metrics.json"]:
        r = client.get(f"/evidence/{path}")
        assert r.status_code in (400, 403, 404), f"Path traversal succeeded on /evidence/{path}"
        assert "SUPER_SECRET_KEY" not in r.text

    # 3. Runs path traversal
    for run_id in ["../../.env", "..%2F..%2F.env", "..\\..\\.env", "..%2F..%2Fruns", "../secret"]:
        r1 = client.get(f"/api/runs/{run_id}")
        assert r1.status_code in (400, 403, 404), f"Path traversal succeeded on /api/runs/{run_id}"
        assert "SUPER_SECRET_KEY" not in r1.text

        r2 = client.get(f"/api/runs/{run_id}/app")
        assert r2.status_code in (400, 403, 404)
        assert "SUPER_SECRET_KEY" not in r2.text

        r3 = client.post(f"/api/replay/{run_id}")
        assert r3.status_code in (400, 403, 404)
        assert "SUPER_SECRET_KEY" not in r3.text


# 17. UI Static Serving
def test_ui_index_and_static_serving(client):
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "POCKET" in r_index.text
    assert "office" in r_index.text
    assert "Cost Radar" in r_index.text
    assert "Verdict" in r_index.text
    assert "Founder" in r_index.text
    assert "Plan" in r_index.text

    r_css = client.get("/ui/style.css")
    assert r_css.status_code == 200
    assert "--paper: #F6F1E7" in r_css.text

    r_office = client.get("/ui/office.js")
    assert r_office.status_code == 200
    assert "PixelOffice" in r_office.text

    r_app = client.get("/ui/app.js")
    assert r_app.status_code == 200
    assert "handleServerEvent" in r_app.text


# 18. STAGE 4c: Failed run status & Approve disabled
def test_failed_run_outcome_and_status(client):
    run_id = "test-failed-rail-run"
    d = config.RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    rec = {
        "run_id": run_id,
        "idea": "Split cafe checks",
        "mode": "baseline",
        "success": False,
        "attempts": 4,
        "first_attempt_passed": False,
        "cost_usd": 0.05,
        "mock": True,
        "approved": False,
        "rails_fired": [{"rail": "attempt_cap", "message": "max attempts reached"}],
    }
    (d / "result.json").write_text(json.dumps(rec), encoding="utf-8")

    # Fetch detail
    res = client.get(f"/api/runs/{run_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["success"] is False
    assert detail["approved"] is False
    assert len(detail["rails_fired"]) == 1
    assert detail["rails_fired"][0]["rail"] == "attempt_cap"

    # Approval must be rejected (409 Conflict)
    r_approve = client.post(f"/api/runs/{run_id}/approve")
    assert r_approve.status_code == 409
    assert "only a run that passed all checks can be approved" in r_approve.json()["detail"].lower()


    # Trust report tracks the rail
    r_trust = client.get(f"/api/trust/{run_id}")
    assert r_trust.status_code == 200
    assert r_trust.json()["approved"] is False
    attempt_rail = next(r for r in r_trust.json()["rails"] if r["rail"] == "Attempt cap")
    assert attempt_rail["fired"] is True


# 19. STAGE 4c: SSE Unbuffered Arrival (first event arrives before run finishes)
@pytest.mark.asyncio
async def test_sse_early_event_arrival_unbuffered():
    import asyncio
    from server.app import RunRequest, start_run

    req = RunRequest(idea="Split bills", mode="baseline", mock=True, mock_delay=0.1)
    res = await start_run(req)
    run_id = res["run_id"]
    stream = hub.get(run_id)
    assert stream is not None

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"/api/runs/{run_id}/events",
        "raw_path": f"/api/runs/{run_id}/events".encode(),
        "query_string": b"",
        "headers": [(b"accept", b"text/event-stream")],
    }

    first_chunk_arrived_while_running = None
    first_event_t = None
    disconnect_event = asyncio.Event()

    async def receive():
        await disconnect_event.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal first_chunk_arrived_while_running, first_event_t
        if message["type"] == "http.response.body":
            body = message.get("body", b"")
            if b"run_started" in body and first_chunk_arrived_while_running is None:
                first_chunk_arrived_while_running = not stream.done
                try:
                    for line in body.decode("utf-8", errors="ignore").splitlines():
                        if line.startswith("data:"):
                            parsed = json.loads(line[5:].strip())
                            if parsed.get("type") == "run_started":
                                first_event_t = parsed.get("t")
                except Exception:
                    pass
                disconnect_event.set()

    try:
        await asyncio.wait_for(app(scope, receive, send), timeout=5.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass

    assert first_chunk_arrived_while_running is True, "First SSE event must arrive before run finishes!"
    assert first_event_t is not None
    assert isinstance(first_event_t, (int, float))
    assert first_event_t >= 0.0


# 20. STAGE 4c: Demo Run Preset and Compare Replay
def test_demo_run_and_compare_replay(client):
    # Verify Demo run 20261011-043610-3f24 on disk contains the autopsy event
    demo_dir = config.RUNS / "20261011-043610-3f24"
    assert demo_dir.exists(), "Demo run folder 20261011-043610-3f24 must exist in runs dir"
    demo_events_file = demo_dir / "events.json"
    assert demo_events_file.exists(), "Demo events.json must exist"
    events = json.loads(demo_events_file.read_text(encoding="utf-8"))
    autopsy_events = [e for e in events if e.get("type") == "autopsy"]
    assert len(autopsy_events) >= 1, "Demo run events.json must contain autopsy event"

    # Replay Demo run synchronously
    r_demo = client.post("/api/replay/20261011-043610-3f24?speed=4&sync=true")
    assert r_demo.status_code == 200
    data_demo = r_demo.json()
    assert "replay_id" in data_demo
    replay_id = data_demo["replay_id"]

    # Read replayed events via SSE stream
    with client.stream("GET", f"/api/runs/{replay_id}/events") as response:
        assert response.status_code == 200
        text = "\n".join(response.iter_lines())
        assert "run_started" in text
        assert "check_failed" in text
        assert "autopsy" in text
        assert "retry" in text
        assert "check_passed" in text
        assert "run_finished" in text
        assert '"replay": true' in text

    # Verify Improved run 20261011-073159-a490 (passed attempt 1)
    improved_dir = config.RUNS / "20261011-073159-a490"
    assert improved_dir.exists(), "Improved run folder 20261011-073159-a490 must exist"
    r_imp = client.post("/api/replay/20261011-073159-a490?speed=4&sync=true")
    assert r_imp.status_code == 200
    imp_replay_id = r_imp.json()["replay_id"]

    with client.stream("GET", f"/api/runs/{imp_replay_id}/events") as response:
        text_imp = "\n".join(response.iter_lines())
        assert "check_passed" in text_imp

        assert "run_finished" in text_imp
        assert '"attempts": 1' in text_imp


# 21. STAGE 4c: Winner Patch Hash Mismatch detection
def test_winner_patch_hash_mismatch(client):
    winner_p = config.PATCH_DIR / "winner.txt"
    original_content = winner_p.read_text(encoding="utf-8")
    try:
        # Overwrite winner.txt with content whose hashes will not match recorded hash in metrics.json
        winner_p.write_text("An entirely different patch text that cannot match recorded SHA\n", encoding="utf-8")

        res = client.get("/api/evidence")
        assert res.status_code == 200
        data = res.json()
        hashes = data["hashes"]

        # When neither file bytes nor stripped prompt text matches recorded hash, report MISMATCH
        assert hashes["winner_patch_match"] == "MISMATCH"
        assert data["winner_patch_match"] == "MISMATCH"
    finally:
        winner_p.write_text(original_content, encoding="utf-8")


