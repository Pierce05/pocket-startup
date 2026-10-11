"""Builder loop: plan -> build -> check -> (diagnose) -> retry, bounded by Trust Rails.

Every exit path (success, failure, rail, exception) writes events.json and result.json.
"""
import asyncio
import json
import re
import time

import config
from agent import autopsy as autopsy_mod
from agent import checks, prompts, rails as rails_mod, sandbox, templates, tracing
from agent.llm import LLM, RunStats, price_for, PRICES
from agent.rails import RailFired, Rails

_HTML_BLOCK = re.compile(r"```html\s*(.*?)```", re.S | re.I)


class ExtractionError(Exception):
    pass


def extract_html(reply: str) -> str:
    m = _HTML_BLOCK.search(reply)
    if m:
        return m.group(1).strip()
    m = re.search(r"(<!doctype html.*?</html>|<html.*?</html>)", reply, re.S | re.I)
    if m:
        return m.group(1).strip()
    raise ExtractionError("no html code block found in the model reply")


def builder_system(mode: str, patch: str | None) -> str:
    if mode == "baseline":
        return prompts.BUILDER_SYSTEM_V1
    if mode == "improved":
        winner = load_winner_patch()
        if patch and winner and patch.strip() == winner.strip():
            return f"{prompts.BUILDER_SYSTEM_V1}\n\n{patch.strip()}"
        return prompts.build_v2(patch)
    if mode in ("candidate_a", "candidate_b") or mode.startswith("candidate_"):
        return f"{prompts.BUILDER_SYSTEM_V1}\n\n{patch}" if patch else prompts.BUILDER_SYSTEM_V1
    raise ValueError(f"mode must be 'baseline', 'improved', or 'candidate_*', got {mode!r}")


def load_winner_patch() -> str | None:
    p = config.PATCH_DIR / "winner.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


async def run_build(idea: str, mode: str, emit=None, *, template: str | None = None,
                    budget_usd: float | None = None, max_attempts: int | None = None,
                    timeout_s: float | None = None, llm: LLM | None = None, rails: Rails | None = None,
                    run_id: str | None = None, patch: str | None = None, autopsy: bool = True,
                    runs_dir=None) -> dict:
    llm = llm or LLM()
    run_id = run_id or sandbox.new_run_id()
    max_attempts = max_attempts or config.DEFAULT_MAX_ATTEMPTS
    rails = rails or Rails(budget_usd or config.DEFAULT_BUDGET_USD, max_attempts, timeout_s or config.DEFAULT_TIMEOUT_S)
    stats = RunStats(model=llm.model)
    tracing.setup()
    tracer = tracing.Tracer(tags=[f"run_id:{run_id}", f"mode:{mode}"], stats=stats)
    events: list[dict] = []
    t0 = time.monotonic()
    state = {
        "success": False, "attempts": 0, "first": False, "error": None,
        "template": template, "approved": False,
        "first_attempt_failed_test": None, "failed_tests": [],
    }
    sandbox.run_dir(run_id, runs_dir)

    def _emit(etype: str, data: dict | None = None):
        known = price_for(llm.model)[2]
        is_mock = bool(llm.mock or llm.model == "mock-model")
        cost_val = round(stats.cost_usd, 8) if (known and stats.cost_usd is not None) else "UNPRICED"
        cost_tag = "MOCK" if is_mock else ("COMPUTED" if known else "UNPRICED")
        ev = {"t": round(time.monotonic() - t0, 3), "type": etype,
              "data": {**(data or {}), "_cost": cost_val, "_cost_tag": cost_tag, "_tokens": stats.tokens}}
        events.append(ev)
        if emit:
            try:
                emit(etype, ev["data"])
            except Exception:  # noqa: BLE001 - a broken listener must never break a run
                pass

    def _fire(rail: str, detail: str):
        rec = rails.fire(rail, detail)
        _emit("rail_fired", rec)

    async def body():
        system = builder_system(mode, patch if patch is not None else (load_winner_patch() if mode == "improved" else None))
        _emit("run_started", {"run_id": run_id, "idea": idea, "mode": mode, "mock": llm.mock,
                              "budget_usd": rails.budget_usd, "max_attempts": rails.max_attempts})
        rails.check_kill()
        spec = await tracer.span("plan", "CHAIN", llm.json_call, prompts.PLANNER_SYSTEM, idea,
                                 stage="plan", stats=stats)
        if template:
            spec["template"] = template
        if spec.get("template") not in templates.TEMPLATES:
            spec["adaptation_note"] = f"{spec.get('template')!r} unsupported, using tip_splitter. " + str(spec.get("adaptation_note", ""))
            spec["template"] = "tip_splitter"
        state["template"] = spec["template"]
        tpl = templates.get(spec["template"])
        rails.check_budget(stats)
        _emit("plan", spec)
        user = prompts.BUILDER_USER.format(spec_json=json.dumps(spec, indent=2), ids=", ".join(tpl.ids),
                                           template_notes=tpl.notes)
        feedback, diagnosed = None, False
        for attempt in range(1, rails.max_attempts + 1):
            rails.check_kill()
            rails.check_time()
            state["attempts"] = attempt
            _emit("attempt_started", {"n": attempt, "of": rails.max_attempts})
            stage = "build" if attempt == 1 else "retry"
            reply = await tracer.span(f"build_attempt_{attempt}", "CHAIN", llm.call, system, feedback or user,
                                      stage=stage, stats=stats, extra_tags=[f"attempt:{attempt}", f"template:{tpl.name}"])
            rails.check_budget(stats)
            try:
                html = extract_html(reply)
            except ExtractionError as e:
                result = checks.Result(False, "extract_html", "one fenced html code block", str(e))
                html = ""
                sandbox.write(run_id, f"attempt_{attempt}_reply.txt", reply, runs_dir)
                path = None
            else:
                path = sandbox.write(run_id, "index.html", html, runs_dir)
                sandbox.write(run_id, f"attempt_{attempt}.html", html, runs_dir)
                _emit("code_written", {"bytes": len(html), "attempt": attempt})
                _emit("check_started", {"attempt": attempt})
                result = await tracer.span("acceptance_check", "TOOL", checks.run, tpl, path,
                                           extra_tags=[f"attempt:{attempt}"])
            if result.passed:
                state["success"] = True
                state["first"] = attempt == 1
                _emit("check_passed", {"attempt": attempt, "console_errors": result.console_errors})
                _emit("awaiting_approval", {"run_id": run_id})
                return
            if attempt == 1 and not state.get("first_attempt_failed_test"):
                state["first_attempt_failed_test"] = result.test
            state.setdefault("failed_tests", []).append(result.test)
            _emit("check_failed", {"attempt": attempt, "test": result.test, "expected": result.expected,
                                   "actual": result.actual, "console_errors": result.console_errors})
            if autopsy and not diagnosed and path is not None:
                diagnosed = True
                try:
                    report = await tracer.span("autopsy", "CHAIN", autopsy_mod.run, llm, stats, tracer.summary(), result, path, template=tpl)
                    sandbox.write_json(run_id, "autopsy.json", report, runs_dir)
                    _emit("autopsy", report)
                    if report.get("autopsy_error"):
                        state["autopsy_error"] = report["autopsy_error"]
                    rails.check_budget(stats)
                except RailFired:
                    raise
                except Exception as e:  # noqa: BLE001
                    state["autopsy_error"] = f"{type(e).__name__}: {e}"
                    _emit("autopsy", {"error": f"{type(e).__name__}: {e}"})
            if attempt < rails.max_attempts:
                retry_ctx = result.as_dict()
                retry_ctx.update({
                    "spec_json": json.dumps(spec, indent=2),
                    "ids": ", ".join(tpl.ids),
                    "template_notes": tpl.notes,
                    "previous_html": html,
                })
                feedback = prompts.RETRY_USER.format(**retry_ctx)
                _emit("retry", {"next": attempt + 1})
        _fire("attempt_cap", f"gave up after {rails.max_attempts} attempts")

    try:
        remaining = max(0.01, rails.timeout_s)
        await asyncio.wait_for(body(), timeout=remaining)
    except RailFired as e:
        _fire(e.rail, e.detail)
    except asyncio.TimeoutError:
        _fire("timeout", f"exceeded {rails.timeout_s}s wall clock")
    except Exception as e:  # noqa: BLE001
        state["error"] = f"{type(e).__name__}: {e}"
    finally:
        record = _finish(run_id, mode, idea, state, stats, rails, tracer, llm, t0, events, runs_dir)
        _emit_final(record, events, emit, run_id, runs_dir)
    return record


def _finish(run_id, mode, idea, state, stats, rails, tracer, llm, t0, events, runs_dir) -> dict:
    known = price_for(llm.model)[2]
    is_mock = bool(llm.mock or llm.model == "mock-model")
    cost_val = round(stats.cost_usd, 8) if (known and stats.cost_usd is not None) else "UNPRICED"
    cost_tag = "MOCK" if is_mock else ("COMPUTED" if known else "UNPRICED")
    record = {
        "run_id": run_id, "mode": mode, "template": state["template"], "idea": idea,
        "success": state["success"], "attempts": state["attempts"], "first_attempt_passed": state["first"],
        "input_tokens": stats.input_tokens, "output_tokens": stats.output_tokens, "tokens": stats.tokens,
        "cost_usd": cost_val, "cost_tag": cost_tag, "cost_by_stage": stats.cost_by_stage(),
        "latency_s": round(time.monotonic() - t0, 3), "rails_fired": rails.fired,
        "error": state["error"], "autopsy_error": state.get("autopsy_error"),
        "first_attempt_failed_test": state.get("first_attempt_failed_test"),
        "failed_tests": state.get("failed_tests", []),
        "neatlogs_trace_url": None, "spans": tracer.summary(),
        "model": llm.model, "temperature": llm.temperature, "pricing_date": PRICES["pricing_date"],
        "pricing_source": "MOCK" if is_mock else PRICES.get("source"),
        "pricing_known_for_model": known, "mock": is_mock,
        "approved": False, "status": "awaiting_approval" if state["success"] else "failed",
    }
    sandbox.write_json(run_id, "result.json", record, runs_dir)
    return record


def _emit_final(record, events, emit, run_id, runs_dir):
    ev = {"t": record["latency_s"], "type": "run_finished", "data": {k: record[k] for k in (
        "run_id", "success", "attempts", "first_attempt_passed", "cost_usd", "cost_tag", "tokens", "latency_s",
        "rails_fired", "error", "mock")}}
    events.append(ev)
    if emit:
        try:
            emit("run_finished", ev["data"])
        except Exception:  # noqa: BLE001
            pass
    sandbox.write_json(run_id, "events.json", events, runs_dir)
    tracing.flush()
