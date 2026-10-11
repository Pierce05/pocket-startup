"""FastAPI app for Pocket Startup: REST APIs + SSE event streaming.

Bound strictly to 127.0.0.1.
Protects against path traversal and secret leakage.
The server never writes to committed evidence or evidence/metrics.json.
"""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

import config
import verdict
from agent import loop, sandbox, tracing
from agent.llm import LLM, PRICES
from agent.rails import Rails
from evidence import metrics as metrics_mod
from server.events import Hub

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@asynccontextmanager
async def lifespan(_app):
    tracing.setup()
    yield


app = FastAPI(title="Pocket Startup", lifespan=lifespan)
hub = Hub()


class RunRequest(BaseModel):
    idea: str
    mode: str = "baseline"
    budget_usd: float | None = None
    template: str | None = None
    mock: bool = False
    sync: bool = False


def validate_run_id(run_id: str) -> str:
    """Validate run_id against path-traversal and malicious characters."""
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(400, "invalid run id")
    if not re.match(r"^[A-Za-z0-9_\-]+$", run_id):
        raise HTTPException(400, "invalid run id format")
    runs_dir = Path(config.RUNS).resolve()
    target = (runs_dir / run_id).resolve()
    if not target.is_relative_to(runs_dir):
        raise HTTPException(403, "access denied")
    return run_id


def _read_result(run_id: str) -> dict[str, Any] | None:
    p = Path(config.RUNS) / run_id / "result.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sha(path: Path | str) -> str | None:
    try:
        p = Path(path)
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() and p.is_file() else None
    except Exception:
        return None


def get_git_log_trailers(n: int = 10) -> list[dict[str, Any]]:
    """Retrieve git trailers from recent commits using read-only git log."""
    trailers = []
    try:
        res = subprocess.run(
            ["git", "log", f"-n{n}", "--format=%H%x1f%h%x1f%s%x1f%(trailers:only)"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(config.ROOT),
        )
        for line in res.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\x1f")
            if len(parts) >= 4:
                commit_hash, short_hash, subject, trailer_text = parts[0], parts[1], parts[2], parts[3].strip()
                parsed_trailers = {}
                if trailer_text:
                    for t_line in trailer_text.splitlines():
                        if ":" in t_line:
                            k, v = t_line.split(":", 1)
                            parsed_trailers[k.strip()] = v.strip()
                trailers.append({
                    "commit": short_hash,
                    "full_hash": commit_hash,
                    "subject": subject,
                    "trailer_raw": trailer_text,
                    "trailers": parsed_trailers,
                })
    except Exception:
        pass
    return trailers


# -------------------------------------------------------------------------
# Health & Configuration (Strictly no secret exposure)
# -------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def get_config():
    return {
        "mock": config.POCKET_MOCK,
        "model": config.GEMINI_MODEL,
        "pricing_date": PRICES.get("pricing_date", "2026-10-11"),
        "has_api_key": bool(config.GEMINI_API_KEY),
        "neatlogs": bool(config.NEATLOGS_API_KEY),
        "default_budget_usd": config.DEFAULT_BUDGET_USD,
        "max_attempts": config.DEFAULT_MAX_ATTEMPTS,
    }


# -------------------------------------------------------------------------
# Runs: Create, List, Inspect, SSE Events, Approve, Kill
# -------------------------------------------------------------------------
@app.post("/api/runs")
async def start_run(req: RunRequest):
    if req.mode not in ("baseline", "improved"):
        raise HTTPException(400, "mode must be baseline or improved")
    if not req.idea or not req.idea.strip():
        raise HTTPException(400, "idea is required")

    is_mock = bool(req.mock or config.POCKET_MOCK)
    if not is_mock and not config.GEMINI_API_KEY:
        raise HTTPException(400, "GEMINI_API_KEY is not set. Add it to .env (or pass mock=true / set POCKET_MOCK=1)")

    if is_mock:
        from agent.mock_llm import MockLLM
        llm = MockLLM()
    else:
        llm = LLM()

    run_id = sandbox.new_run_id()
    stream = hub.create(run_id)
    budget = req.budget_usd if req.budget_usd is not None else config.DEFAULT_BUDGET_USD
    rails = Rails(budget, config.DEFAULT_MAX_ATTEMPTS, config.DEFAULT_TIMEOUT_S)
    stream.rails = rails
    loop_ref = asyncio.get_running_loop()

    def emit(etype, data):
        loop_ref.create_task(stream.publish(etype, data))

    async def runner():
        try:
            rec = await loop.run_build(
                req.idea,
                req.mode,
                emit,
                template=req.template,
                rails=rails,
                llm=llm,
                run_id=run_id,
            )
            await asyncio.sleep(0)
            try:
                cur = json.loads(Path(config.METRICS_PATH).read_text(encoding="utf-8")) if Path(config.METRICS_PATH).exists() else {}
                await stream.publish("metrics_ready", cur.get("live", {}))
            except Exception:
                pass
            try:
                fp = verdict.resolve_founder_path("a")
                f_prof = verdict.load_founder_profile(fp)
                assumptions = config.load_assumptions()
                arm = (cur.get("experiment", {}).get("held_out", {}).get("improved")
                       or cur.get("experiment", {}).get("combined", {}).get("improved")
                       or cur.get("live") or {})
                v = verdict.compute(arm, assumptions, f_prof)
                await stream.publish("verdict_ready", v)
            except Exception:
                pass
            return rec
        finally:
            await stream.finish()

    stream.runner = runner
    if req.sync:
        await runner()
    else:
        stream.task = asyncio.create_task(runner())
    return {"run_id": run_id}


@app.get("/api/runs")
def list_runs():
    """List recent runs with outcome."""
    base = Path(config.RUNS)
    out = []
    if not base.exists():
        return out
    for p in sorted(base.glob("*/result.json"), reverse=True):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "run_id": r.get("run_id", p.parent.name),
                "idea": r.get("idea"),
                "mode": r.get("mode"),
                "success": r.get("success"),
                "attempts": r.get("attempts"),
                "first_attempt_passed": r.get("first_attempt_passed"),
                "cost_usd": r.get("cost_usd"),
                "mock": bool(r.get("mock") or r.get("cost_tag") == "MOCK" or r.get("model") == "mock-model"),
                "approved": bool(r.get("approved")),
            })
        except Exception:
            continue
    return out


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    """SSE stream of the loop's events."""
    valid_id = validate_run_id(run_id)
    s = hub.get(valid_id)
    if s is None:
        raise HTTPException(404, "no live stream for this run id (start a replay instead)")
    return EventSourceResponse(s.iterate())


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """Get single run record."""
    valid_id = validate_run_id(run_id)
    rec = _read_result(valid_id)
    if rec:
        return rec
    if hub.get(valid_id):
        return {"run_id": valid_id, "status": "running"}
    raise HTTPException(404, "unknown run")


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str):
    """Approve a run after it passed all checks."""
    valid_id = validate_run_id(run_id)
    rec = _read_result(valid_id)
    if not rec:
        raise HTTPException(404, "run not finished or unknown")
    if not rec.get("success"):
        raise HTTPException(409, "only a run that passed all checks can be approved")
    rec["approved"] = True
    rec["status"] = "approved"
    p = Path(config.RUNS) / valid_id / "result.json"
    p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    s = hub.get(valid_id)
    if s:
        await s.publish("approved", {"run_id": valid_id})
    return rec


@app.post("/api/runs/{run_id}/kill")
async def kill(run_id: str):
    """Operator kill switch for a running agent loop."""
    valid_id = validate_run_id(run_id)
    s = hub.get(valid_id)
    if not s or not s.rails:
        raise HTTPException(404, "no live run with this id")
    s.rails.kill()
    return {"killed": True, "run_id": valid_id}


# -------------------------------------------------------------------------
# Replay Mode
# -------------------------------------------------------------------------
@app.post("/api/replay/{run_id}")
async def replay(run_id: str, speed: float = Query(1.0), sync: bool = Query(False)):
    """Replay stored events.json at speed 1, 2, or 4."""
    valid_id = validate_run_id(run_id)
    p = Path(config.RUNS) / valid_id / "events.json"
    if not p.exists():
        raise HTTPException(404, "no events.json for this run")
    if speed not in (1, 2, 4, 1.0, 2.0, 4.0):
        raise HTTPException(400, "speed must be 1, 2 or 4")

    events = json.loads(p.read_text(encoding="utf-8"))
    rid = f"replay-{valid_id}-{sandbox.new_run_id()[-4:]}"
    stream = hub.create(rid, replay=True)

    async def feeder():
        prev = 0.0
        try:
            for ev in events:
                t = ev.get("t") or 0.0
                delay = 0.0 if sync else min(max(t - prev, 0.0), 3.0) / speed
                if delay > 0:
                    await asyncio.sleep(delay)
                prev = t
                await stream.publish(ev.get("type", "ev"), ev.get("data", {}), t)
        finally:
            await stream.finish()

    stream.feeder = feeder
    if sync:
        await feeder()
    else:
        stream.task = asyncio.create_task(feeder())
    return {"replay_id": rid, "events": len(events), "speed": speed}


# -------------------------------------------------------------------------
# Read-Only Metrics, Verdict, Ledger, Evidence, Plan
# -------------------------------------------------------------------------
@app.get("/api/metrics")
def get_metrics():
    """Read evidence/metrics.json strictly read-only."""
    p = Path(config.METRICS_PATH)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/verdict")
def get_verdict(founder: str = "a", cohort: str = "held_out"):
    """Evaluate deterministic viability verdict rules without calling any LLM."""
    fp = verdict.resolve_founder_path(founder)
    founder_profile = verdict.load_founder_profile(fp)
    assumptions = config.load_assumptions()

    mp = Path(config.METRICS_PATH)
    metrics = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    exp = metrics.get("experiment", {})
    arm = exp.get(cohort, {}).get("improved")
    if not arm and exp:
        arm = exp.get("held_out", {}).get("improved") or exp.get("combined", {}).get("improved") or {}
    if not arm:
        arm = metrics.get("live", {})

    return verdict.compute(arm, assumptions, founder_profile)


@app.post("/api/founder/verdict")
@app.post("/api/verdict")
def evaluate_custom_founder_verdict(req: dict[str, Any]):
    """Evaluate deterministic verdict with a custom founder profile from intake form."""
    cohort = str(req.get("cohort") or "held_out")
    base_name = str(req.get("founder_base") or "a")
    fp = verdict.resolve_founder_path(base_name)
    founder_profile = verdict.load_founder_profile(fp)

    # Override any supplied fields
    for k in (
        "target_user",
        "payer",
        "goal",
        "first_customer_channel",
        "demand_evidence",
        "budget_inr",
        "weekly_hours",
        "skills",
        "price_per_run_inr",
    ):
        if k in req and req[k] is not None and req[k] != "":
            founder_profile[k] = req[k]

    # Type coercions
    if "budget_inr" in founder_profile:
        try:
            founder_profile["budget_inr"] = float(founder_profile["budget_inr"])
        except (ValueError, TypeError):
            raise HTTPException(400, "budget_inr must be a number")
    if "weekly_hours" in founder_profile:
        try:
            founder_profile["weekly_hours"] = float(founder_profile["weekly_hours"])
        except (ValueError, TypeError):
            raise HTTPException(400, "weekly_hours must be a number")
    if "price_per_run_inr" in founder_profile:
        try:
            founder_profile["price_per_run_inr"] = float(founder_profile["price_per_run_inr"])
        except (ValueError, TypeError):
            raise HTTPException(400, "price_per_run_inr must be a number")
    if isinstance(founder_profile.get("skills"), str):
        founder_profile["skills"] = [s.strip() for s in founder_profile["skills"].split(",") if s.strip()]

    try:
        verdict.validate_founder(founder_profile)
    except ValueError as err:
        raise HTTPException(400, str(err))

    assumptions = config.load_assumptions()
    mp = Path(config.METRICS_PATH)
    metrics = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    exp = metrics.get("experiment", {})
    arm = exp.get(cohort, {}).get("improved")
    if not arm and exp:
        arm = exp.get("held_out", {}).get("improved") or exp.get("combined", {}).get("improved") or {}
    if not arm:
        arm = metrics.get("live", {})

    return verdict.compute(arm, assumptions, founder_profile)


@app.get("/api/ledger")
def get_ledger():
    """Read or generate evidence ledger."""
    p = Path(config.LEDGER_PATH)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return verdict.generate_ledger()


@app.get("/api/evidence")
def get_evidence():
    """Evidence Locker data: claims, file hashes, cell counts, git trailers, and reproduce commands."""
    mp = Path(config.METRICS_PATH)
    m = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    exp = m.get("experiment", {})

    runs_dir = Path(config.RUNS)
    real_runs = []
    rails_runs = []
    autopsy_files = []
    if runs_dir.exists():
        for p in runs_dir.glob("*/result.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
                if not (r.get("mock") or r.get("cost_tag") == "MOCK" or r.get("model") == "mock-model"):
                    real_runs.append(r)
                if r.get("rails_fired"):
                    rails_runs.append(r.get("run_id", p.parent.name))
            except Exception:
                pass
        for a in runs_dir.glob("*/autopsy.json"):
            autopsy_files.append(str(a.relative_to(config.ROOT) if a.is_relative_to(config.ROOT) else a.name))

    entire_files = []
    entire_dir = Path(config.EVIDENCE) / "entire"
    if entire_dir.exists():
        for f in entire_dir.glob("*"):
            if f.name != ".gitkeep":
                entire_files.append(f.name)

    cfo_dir = Path(config.CFO_DIR)
    cfo_exports = []
    if cfo_dir.exists():
        for f in cfo_dir.glob("*"):
            if f.name not in ("cfo_input.md", ".gitkeep"):
                cfo_exports.append(f.name)

    cfo_input_exists = (cfo_dir / "cfo_input.md").exists()
    links = m.get("neatlogs_trace_links", {})

    claims = [
        {
            "claim": "The agent completes tasks end to end",
            "status": "FOUND" if len(real_runs) > 0 else "MISSING",
            "proof": [
                {
                    "label": f"{len(real_runs)} real run folders",
                    "ref": "evidence/runs/",
                    "status": "FOUND" if len(real_runs) > 0 else "MISSING",
                }
            ],
        },
        {
            "claim": "A failure was diagnosed from the trace",
            "status": "FOUND" if (autopsy_files or links.get("baseline_failure")) else "MISSING",
            "proof": [
                {
                    "label": "autopsy.json files",
                    "ref": ", ".join(autopsy_files[:4]) or "none yet",
                    "status": "FOUND" if autopsy_files else "MISSING",
                },
                {
                    "label": "neatlogs trace (baseline failure)",
                    "ref": links.get("baseline_failure") or "",
                    "status": "FOUND" if links.get("baseline_failure") else "MISSING",
                },
            ],
        },
        {
            "claim": "The fix improved results (tuning set)",
            "status": "FOUND" if "tuning" in exp else "MISSING",
            "proof": [
                {
                    "label": "metrics.json experiment.tuning",
                    "ref": "evidence/metrics.json",
                    "status": "FOUND" if "tuning" in exp else "MISSING",
                }
            ],
        },
        {
            "claim": "The fix holds on unseen ideas (held-out set)",
            "status": "FOUND" if "held_out" in exp else "MISSING",
            "proof": [
                {
                    "label": "metrics.json experiment.held_out",
                    "ref": "evidence/metrics.json",
                    "status": "FOUND" if "held_out" in exp else "MISSING",
                }
            ],
        },
        {
            "claim": "Trust Rails work",
            "status": "FOUND" if len(rails_runs) > 0 else "MISSING",
            "proof": [
                {
                    "label": "runs where a rail fired",
                    "ref": ", ".join(rails_runs[:4]) or "none yet",
                    "status": "FOUND" if len(rails_runs) > 0 else "MISSING",
                }
            ],
        },
        {
            "claim": "Entire checkpoints were used",
            "status": "FOUND" if len(entire_files) > 0 else "MISSING",
            "proof": [
                {
                    "label": "checkpoint screenshots",
                    "ref": ", ".join(entire_files[:4]) or "evidence/entire/",
                    "status": "FOUND" if len(entire_files) > 0 else "MISSING",
                }
            ],
        },
        {
            "claim": "cfo.ai plan came from measured data",
            "status": "FOUND" if (cfo_input_exists or len(cfo_exports) > 0) else "MISSING",
            "proof": [
                {
                    "label": "cfo_input.md",
                    "ref": "evidence/cfo/cfo_input.md",
                    "status": "FOUND" if cfo_input_exists else "MISSING",
                },
                {
                    "label": "exported plan",
                    "ref": ", ".join(cfo_exports[:4]) or "evidence/cfo/",
                    "status": "FOUND" if len(cfo_exports) > 0 else "MISSING",
                },
            ],
        },
    ]

    hashes = {
        "evidence/metrics.json": _sha(config.METRICS_PATH),
        "evidence/patches/winner.txt": _sha(config.PATCH_DIR / "winner.txt"),
        "winner.txt": _sha(config.PATCH_DIR / "winner.txt"),
        "agent/prompts.py": _sha(config.ROOT / "agent" / "prompts.py"),
        "assumptions.yaml": _sha(config.ASSUMPTIONS_PATH),
        "verdict.py": _sha(config.ROOT / "verdict.py"),
    }

    cell_run_ids = m.get("cell_run_ids", {})
    run_counts_per_cell = {
        "tuning/baseline": len(cell_run_ids.get("tuning/baseline", [])) or exp.get("tuning", {}).get("baseline", {}).get("n_runs", 0),
        "tuning/improved": len(cell_run_ids.get("tuning/improved", [])) or exp.get("tuning", {}).get("improved", {}).get("n_runs", 0),
        "held_out/baseline": len(cell_run_ids.get("held_out/baseline", [])) or exp.get("held_out", {}).get("baseline", {}).get("n_runs", 0),
        "held_out/improved": len(cell_run_ids.get("held_out/improved", [])) or exp.get("held_out", {}).get("improved", {}).get("n_runs", 0),
    }

    reproduce = [
        "python -m experiments.smoke --mode baseline --n 5",
        "python -m experiments.patch_lab",
        "python -m experiments.ab --repeats 4 --seed 42 --sleep 1.0",
        "python -m cfo.bridge",
        "python verdict.py --founder a",
        "pytest -q",
    ]

    trailers = get_git_log_trailers(10)

    return {
        "claims": claims,
        "hashes": hashes,
        "run_counts_per_cell": run_counts_per_cell,
        "cell_counts": run_counts_per_cell,
        "reproduce_commands": reproduce,
        "reproduce": reproduce,
        "git_log_trailers": trailers,
        "trailers": trailers,
        "pricing_date": PRICES.get("pricing_date", "2026-10-11"),
    }


@app.get("/api/plan")
def get_plan():
    """Return plan_numbers.json and plan_summary.md if present, else PENDING."""
    numbers_p = Path(config.CFO_DIR) / "plan_numbers.json"
    summary_p = Path(config.CFO_DIR) / "plan_summary.md"
    input_p = Path(config.CFO_DIR) / "cfo_input.md"

    plan_numbers = json.loads(numbers_p.read_text(encoding="utf-8")) if numbers_p.exists() else "PENDING"
    plan_summary = summary_p.read_text(encoding="utf-8") if summary_p.exists() else "PENDING"
    cfo_input = input_p.read_text(encoding="utf-8") if input_p.exists() else "PENDING"

    status = "READY" if (numbers_p.exists() and summary_p.exists()) else "PENDING"

    exports = []
    if Path(config.CFO_DIR).exists():
        exports = sorted(x.name for x in Path(config.CFO_DIR).glob("*") if x.name not in ("cfo_input.md", ".gitkeep"))

    return {
        "status": status,
        "plan_numbers": plan_numbers,
        "plan_summary": plan_summary,
        "cfo_input": cfo_input,
        "exports": exports,
    }


# -------------------------------------------------------------------------
# App inspection & Trust report
# -------------------------------------------------------------------------
@app.get("/api/runs/{run_id}/app")
def built_app(run_id: str):
    valid_id = validate_run_id(run_id)
    p = Path(config.RUNS) / valid_id / "index.html"
    if not p.exists():
        raise HTTPException(404, "no built app for this run")
    return HTMLResponse(
        p.read_text(encoding="utf-8"),
        headers={"Content-Security-Policy": "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"},
    )


@app.get("/api/trust/{run_id}")
def trust(run_id: str):
    valid_id = validate_run_id(run_id)
    rec = _read_result(valid_id)
    if not rec:
        raise HTTPException(404, "unknown run")
    fired = {r.get("rail") for r in rec.get("rails_fired", []) if isinstance(r, dict)}
    def row(name, desc, key=None):
        return {"rail": name, "description": desc, "fired": (key in fired) if key else False}
    return {
        "run_id": valid_id,
        "rails": [
            row("Budget cap", f"hard USD cap per run (default ${config.DEFAULT_BUDGET_USD})", "budget"),
            row("Attempt cap", f"at most {config.DEFAULT_MAX_ATTEMPTS} build attempts", "attempt_cap"),
            row("Wall-clock timeout", f"{config.DEFAULT_TIMEOUT_S}s per run", "timeout"),
            row("Kill switch", "operator can stop a live run", "kill_switch"),
            row("Sandbox", "network blocked, 15s check timeout, generated code only runs in headless Chromium"),
            row("Human approval", "build stays unapproved until a person clicks Approve"),
        ],
        "approved": bool(rec.get("approved")),
        "fired": rec.get("rails_fired", []),
    }


# -------------------------------------------------------------------------
# Secure File Serving (evidence/ and ui/ with Path-Traversal Protection)
# -------------------------------------------------------------------------
@app.get("/")
def index():
    ui_index = Path(config.ROOT) / "ui" / "index.html"
    if ui_index.exists():
        return FileResponse(ui_index)
    return {"message": "Pocket Startup API"}


@app.get("/ui/{file_path:path}")
def serve_ui(file_path: str):
    if ".." in file_path or file_path.startswith("/") or file_path.startswith("\\"):
        raise HTTPException(400, "invalid path")
    ui_dir = (Path(config.ROOT) / "ui").resolve()
    target = (ui_dir / file_path).resolve()
    if not target.is_relative_to(ui_dir) or not target.exists() or not target.is_file():
        raise HTTPException(404, "file not found")
    if target.name.startswith(".env") or ".env" in target.parts:
        raise HTTPException(403, "access denied")
    return FileResponse(target)


@app.get("/evidence/{file_path:path}")
def serve_evidence(file_path: str):
    if ".." in file_path or file_path.startswith("/") or file_path.startswith("\\"):
        raise HTTPException(400, "invalid path")
    ev_dir = Path(config.EVIDENCE).resolve()
    target = (ev_dir / file_path).resolve()
    if not target.is_relative_to(ev_dir) or not target.exists() or not target.is_file():
        raise HTTPException(404, "file not found")
    if target.name.startswith(".env") or ".env" in target.parts:
        raise HTTPException(403, "access denied")
    return FileResponse(target)


def run_server():
    """Start uvicorn server binding to 127.0.0.1:8000."""
    import uvicorn
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run_server()
