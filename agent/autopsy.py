"""Flight Recorder: reads a failed run and writes a crash report.

Robust execution: requests JSON output from Gemini, strips code fences, validates keys,
retries once on parse/validation failure, and records autopsy_error without crashing.
"""
import json
import re
from pathlib import Path

from agent import templates
from agent.prompts import AUTOPSY_SYSTEM

HTML_LIMIT = 6000
REQUIRED_KEYS = {"failed_span", "root_cause", "evidence", "recommended_prompt_change", "confidence"}


def _check_ids(html: str, selectors: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Determine which required template selectors exist in the HTML string."""
    present, missing = [], []
    for sel in selectors:
        if sel.startswith("#"):
            target_id = sel[1:]
            pattern = rf'\bid\s*=\s*["\']?{re.escape(target_id)}["\'\s>]'
            if re.search(pattern, html, re.I):
                present.append(sel)
            else:
                missing.append(sel)
        elif sel.startswith("."):
            target_class = sel[1:]
            pattern = rf'\bclass\s*=\s*["\'][^"\']*\b{re.escape(target_class)}\b[^"\']*["\']'
            if re.search(pattern, html, re.I):
                present.append(sel)
            else:
                missing.append(sel)
        else:
            if sel in html:
                present.append(sel)
            else:
                missing.append(sel)
    return present, missing


def build_input(trace_summary: list, result, html_path, template=None) -> str:
    """Build the autopsy prompt payload containing trace spans, check failure, HTML, and required IDs."""
    html = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    tpl_obj = None
    if template:
        tpl_name = getattr(template, "name", template)
        if tpl_name in templates.TEMPLATES:
            tpl_obj = templates.get(tpl_name)
    if not tpl_obj:
        for span in trace_summary:
            for tag in span.get("tags", []):
                if tag.startswith("template:"):
                    name = tag.split(":", 1)[1]
                    if name in templates.TEMPLATES:
                        tpl_obj = templates.get(name)
                        break
            if tpl_obj:
                break
    if not tpl_obj:
        tpl_obj = templates.get("tip_splitter")

    present_ids, missing_ids = _check_ids(html, tpl_obj.ids)

    return json.dumps({
        "spans": trace_summary,
        "failed_check": {
            "test": result.test,
            "expected": result.expected,
            "actual": result.actual,
            "console_errors": result.console_errors,
        },
        "required_ids_present": present_ids,
        "required_ids_missing": missing_ids,
        "generated_index_html": html[:HTML_LIMIT],
        "html_truncated": len(html) > HTML_LIMIT,
    }, indent=2)


def parse_and_validate(text: str) -> dict:
    """Strip code fences, parse JSON, and validate required keys."""
    t = text.strip()
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S | re.I).strip()
    data = None
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    if not isinstance(data, dict):
        raise ValueError(f"autopsy reply is not a valid JSON object: {text[:200]!r}")

    missing_keys = REQUIRED_KEYS - set(data.keys())
    if missing_keys:
        raise ValueError(f"autopsy JSON missing required keys: {sorted(missing_keys)}")
    return data


async def run(llm, stats, trace_summary: list, result, html_path, template=None) -> dict:
    """Run autopsy with retry on parse failure and non-crashing fallback."""
    from agent.rails import RailFired

    payload = build_input(trace_summary, result, html_path, template=template)
    last_err: Exception | None = None

    for attempt in range(2):  # 1 initial attempt + 1 retry on parse failure
        try:
            # Request JSON output (json_mode=True sets response_mime_type="application/json")
            reply = await llm.json_call(AUTOPSY_SYSTEM, payload, stage="autopsy", stats=stats)
            if isinstance(reply, dict):
                missing = REQUIRED_KEYS - set(reply.keys())
                if missing:
                    raise ValueError(f"autopsy JSON missing required keys: {sorted(missing)}")
                return reply
            if isinstance(reply, str):
                return parse_and_validate(reply)
            raise ValueError(f"autopsy did not return a dict: {type(reply).__name__}")
        except RailFired:
            raise
        except Exception as e:
            last_err = e

    # Record autopsy_error in the run without crashing
    err_msg = f"{type(last_err).__name__}: {last_err}"
    return {
        "autopsy_error": err_msg,
        "failed_span": "acceptance_check",
        "root_cause": f"Autopsy failed to parse model output: {err_msg}",
        "evidence": [f"failed test: {result.test}", f"actual: {result.actual}"],
        "recommended_prompt_change": "Fix check failure.",
        "confidence": "low",
    }
