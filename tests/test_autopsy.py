import json
import re
from pathlib import Path

import pytest

from agent import autopsy, checks, templates
from agent.llm import LLM, LLMError


def test_build_input_contains_required_fields(tmp_path):
    p = tmp_path / "index.html"
    p.write_text(
        "<!doctype html><html><body>"
        "<input id='bill'><input id='people'><input id='tip'><button id='calc'></button>"
        "<div id='error'></div>"  # Missing #result
        "</body></html>",
        encoding="utf-8",
    )
    res = checks.Result(False, "split_basic", "30.00 in #result", "#result empty", ["console error 1"])
    spans = [{"name": "acceptance_check", "status": "failed", "tags": ["template:tip_splitter"]}]

    payload_str = autopsy.build_input(spans, res, p)
    data = json.loads(payload_str)

    assert "spans" in data
    assert data["failed_check"]["test"] == "split_basic"
    assert data["failed_check"]["expected"] == "30.00 in #result"
    assert data["failed_check"]["actual"] == "#result empty"
    assert data["failed_check"]["console_errors"] == ["console error 1"]
    assert "generated_index_html" in data
    assert "required_ids_present" in data
    assert "required_ids_missing" in data

    # #result is missing in the HTML above
    assert "#result" in data["required_ids_missing"]
    assert "#bill" in data["required_ids_present"]


def test_parse_and_validate_strips_code_fences_and_checks_keys():
    fenced = """```json
    {
      "failed_span": "acceptance_check",
      "root_cause": "Division by zero.",
      "evidence": ["people was 0"],
      "recommended_prompt_change": "Check people > 0.",
      "confidence": "high"
    }
    ```"""
    res = autopsy.parse_and_validate(fenced)
    assert res["failed_span"] == "acceptance_check"
    assert res["confidence"] == "high"

    # Missing key raises ValueError
    missing_key = """{"failed_span": "acceptance_check"}"""
    with pytest.raises(ValueError, match="missing required keys"):
        autopsy.parse_and_validate(missing_key)


class FailOnceLLM(LLM):
    def __init__(self, fail_reply: str, valid_reply: dict):
        super().__init__(model="mock-model")
        self.mock = True
        self.calls = 0
        self.fail_reply = fail_reply
        self.valid_reply = valid_reply

    async def json_call(self, system, user, stage="autopsy", stats=None):
        self.calls += 1
        if self.calls == 1:
            raise LLMError(f"model did not return valid JSON: {self.fail_reply!r}")
        return self.valid_reply


class AlwaysFailLLM(LLM):
    def __init__(self, fail_reply: str):
        super().__init__(model="mock-model")
        self.mock = True
        self.calls = 0
        self.fail_reply = fail_reply

    async def json_call(self, system, user, stage="autopsy", stats=None):
        self.calls += 1
        raise LLMError(f"model did not return valid JSON: {self.fail_reply!r}")


@pytest.mark.asyncio
async def test_autopsy_retries_on_parse_failure(tmp_path):
    p = tmp_path / "index.html"
    p.write_text("<html></html>", encoding="utf-8")
    res = checks.Result(False, "t", "e", "a")
    valid_data = {
        "failed_span": "acceptance_check",
        "root_cause": "Div by zero.",
        "evidence": ["err"],
        "recommended_prompt_change": "Validate input.",
        "confidence": "high",
    }
    llm = FailOnceLLM("truncated {", valid_data)

    report = await autopsy.run(llm, None, [], res, p)
    assert llm.calls == 2
    assert report["root_cause"] == "Div by zero."
    assert "autopsy_error" not in report


@pytest.mark.asyncio
async def test_autopsy_final_failure_does_not_crash(tmp_path):
    p = tmp_path / "index.html"
    p.write_text("<html></html>", encoding="utf-8")
    res = checks.Result(False, "t", "e", "a")
    llm = AlwaysFailLLM("completely broken json")

    report = await autopsy.run(llm, None, [], res, p)
    assert llm.calls == 2
    assert "autopsy_error" in report
    assert "LLMError" in report["autopsy_error"]
    assert report["failed_span"] == "acceptance_check"


@pytest.mark.asyncio
async def test_failing_reply_from_run_40b9(tmp_path):
    # Check if run 20261011-043734-40b9 events.json exists on disk
    events_path = Path("evidence/runs/20261011-043734-40b9/events.json")
    if not events_path.exists():
        pytest.skip("Run 20261011-043734-40b9 not found on disk")

    events = json.loads(events_path.read_text(encoding="utf-8"))
    failing_text = None
    for ev in events:
        if ev.get("type") == "autopsy" and "error" in ev.get("data", {}):
            err_msg = ev["data"]["error"]
            m = re.search(r"valid JSON:\s*'(.*)'\s*$", err_msg, re.S)
            if m:
                failing_text = m.group(1).replace("\\n", "\n")
                break

    assert failing_text is not None, "Could not extract failing reply from 40b9 events.json"

    p = tmp_path / "index.html"
    p.write_text("<html></html>", encoding="utf-8")
    res = checks.Result(False, "fractional_people", "error visible", "error visible=False")

    valid_data = {
        "failed_span": "acceptance_check",
        "root_cause": "Fractional people count was not validated.",
        "evidence": ["actual shows error visible=False"],
        "recommended_prompt_change": "Check Math.floor(people) === people.",
        "confidence": "high",
    }

    # Test recovery on retry
    llm_recover = FailOnceLLM(failing_text, valid_data)
    rep_recover = await autopsy.run(llm_recover, None, [], res, p)
    assert llm_recover.calls == 2
    assert rep_recover["root_cause"] == "Fractional people count was not validated."

    # Test graceful fallback on persistent failure
    llm_fail = AlwaysFailLLM(failing_text)
    rep_fail = await autopsy.run(llm_fail, None, [], res, p)
    assert llm_fail.calls == 2
    assert "autopsy_error" in rep_fail
    assert "acceptance_check" == rep_fail["failed_span"]
