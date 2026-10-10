import json

import pytest

import config
from agent import loop, tracing
from agent.mock_llm import MockLLM
from agent.rails import Rails
from tests.conftest import needs_browser


def test_extract_html_variants():
    assert loop.extract_html("hi\n```html\n<p>x</p>\n```") == "<p>x</p>"
    assert loop.extract_html("<!doctype html><html><body>y</body></html>").endswith("</html>")
    with pytest.raises(loop.ExtractionError):
        loop.extract_html("no code here")


def test_builder_system_modes():
    assert "edge cases" not in loop.builder_system("baseline", None)
    v2 = loop.builder_system("improved", "Always show #error.")
    assert "edge cases" in v2 and "Always show #error." in v2
    with pytest.raises(ValueError):
        loop.builder_system("nope", None)


@needs_browser
async def test_full_run_mock_fails_then_succeeds_and_writes_evidence():
    events = []
    rec = await loop.run_build("split a bill", "baseline", lambda t, d: events.append(t), llm=MockLLM(), template="tip_splitter")
    assert rec["success"] and rec["attempts"] == 2 and not rec["first_attempt_passed"]
    assert rec["mock"] is True
    for needed in ("run_started", "plan", "attempt_started", "code_written", "check_started", "check_failed",
                   "autopsy", "retry", "check_passed", "awaiting_approval", "run_finished"):
        assert needed in events, needed
    d = config.RUNS / rec["run_id"]
    assert (d / "index.html").exists() and (d / "events.json").exists() and (d / "result.json").exists()
    assert (d / "autopsy.json").exists()
    assert set(rec["cost_by_stage"]) >= {"plan", "build", "retry", "autopsy"}


@needs_browser
async def test_improved_mode_passes_first_attempt():
    rec = await loop.run_build("split a bill", "improved", llm=MockLLM(), template="tip_splitter", autopsy=False)
    assert rec["success"] and rec["first_attempt_passed"] and rec["attempts"] == 1


async def test_tiny_budget_rail_stops_cleanly_and_records_which_rail():
    events = []
    rec = await loop.run_build("split a bill", "baseline", lambda t, d: events.append((t, d)), llm=MockLLM(),
                               template="tip_splitter", budget_usd=1e-12)
    assert not rec["success"]
    assert [r["rail"] for r in rec["rails_fired"]] == ["budget"]
    assert any(t == "rail_fired" for t, _ in events)
    assert (config.RUNS / rec["run_id"] / "result.json").exists()  # result.json on every exit path


async def test_kill_switch_rail():
    rails = Rails(1.0, 4, 60)
    rails.kill()
    rec = await loop.run_build("x", "baseline", llm=MockLLM(), rails=rails)
    assert [r["rail"] for r in rec["rails_fired"]] == ["kill_switch"] and not rec["success"]


async def test_wall_clock_timeout_rail():
    class SlowLLM(MockLLM):
        async def _raw(self, *a, **k):
            import asyncio
            await asyncio.sleep(2)
            return await super()._raw(*a, **k)

    rec = await loop.run_build("x", "baseline", llm=SlowLLM(), timeout_s=0.2)
    assert [r["rail"] for r in rec["rails_fired"]] == ["timeout"]


async def test_exception_still_writes_result_with_error():
    class Boom(MockLLM):
        async def _raw(self, *a, **k):
            raise RuntimeError("kaput")

    rec = await loop.run_build("x", "baseline", llm=Boom())
    assert not rec["success"] and "kaput" in rec["error"]
    assert json.loads((config.RUNS / rec["run_id"] / "result.json").read_text(encoding="utf-8"))["error"]


@needs_browser
async def test_attempt_cap_rail():
    class AlwaysBad(MockLLM):
        async def _raw(self, system, user, json_mode):
            if "Founder step" in system or "Flight Recorder" in system:
                return await super()._raw(system, user, json_mode)
            from agent.mock_llm import FIX
            return "```html\n" + (FIX / "bad_tip.html").read_text(encoding="utf-8") + "\n```", 10, 10

    rec = await loop.run_build("x", "baseline", llm=AlwaysBad(), template="tip_splitter", max_attempts=2, autopsy=False)
    assert not rec["success"] and rec["attempts"] == 2
    assert [r["rail"] for r in rec["rails_fired"]] == ["attempt_cap"]


async def test_local_spans_recorded_for_autopsy():
    rec = await loop.run_build("x", "baseline", llm=MockLLM(), template="tip_splitter", budget_usd=1e-12)
    names = [s["name"] for s in rec["spans"]]
    assert "plan" in names
