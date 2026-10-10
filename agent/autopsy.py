"""Flight Recorder: ONE LLM call (not a second agent) that reads a failed run and writes a crash report."""
import json
from pathlib import Path

from agent.prompts import AUTOPSY_SYSTEM

HTML_LIMIT = 6000


def build_input(trace_summary: list, result, html_path) -> str:
    html = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    return json.dumps({
        "spans": trace_summary,
        "failed_check": {
            "test": result.test, "expected": result.expected,
            "actual": result.actual, "console_errors": result.console_errors,
        },
        "generated_index_html": html[:HTML_LIMIT],
        "html_truncated": len(html) > HTML_LIMIT,
    }, indent=2)


async def run(llm, stats, trace_summary: list, result, html_path) -> dict:
    payload = build_input(trace_summary, result, html_path)
    report = await llm.json_call(AUTOPSY_SYSTEM, payload, stage="autopsy", stats=stats)
    if not isinstance(report, dict):
        raise ValueError("autopsy did not return a JSON object")
    return report
