"""MOCK LLM for tests and offline UI development ONLY.

Runs that use it are labelled mock=true and are excluded from every metric. The mock's first baseline
attempt is deliberately buggy so the failure -> diagnose -> fix path can be exercised in tests.
It must never be used in experiments (experiments/ab.py refuses it).
"""
import json
from pathlib import Path

from agent.llm import LLM

FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _tok(s: str) -> int:
    return max(1, len(s) // 4)


class MockLLM(LLM):
    def __init__(self, **kw):
        super().__init__(model="mock-model", **kw)
        self.mock = True

    async def _raw(self, system, user, json_mode):
        if "Founder step" in system:
            text = json.dumps({
                "template": "tip_splitter", "product_name": "SplitEasy",
                "one_line_pitch": "Split any bill in two taps.", "target_user": "friends dining out",
                "adaptation_note": "none (MOCK)",
            })
        elif "Flight Recorder" in system:
            text = json.dumps({
                "failed_span": "acceptance_check",
                "root_cause": "The code divides by the people count without checking it is greater than zero. (MOCK)",
                "evidence": ["check expected #error visible", "generated code computes bill / people directly"],
                "recommended_prompt_change": "Validate every numeric input and show a message in #error before dividing.",
                "confidence": "medium",
            })
        elif "generalizes the common lesson" in system:
            text = json.dumps({"patch": "Validate all numeric inputs (zero, negative, blank, non-numeric) and show a message in #error."})
        else:
            good = "previous attempt failed" in user or "edge cases" in system
            html = (FIX / ("good_tip.html" if good else "bad_tip.html")).read_text(encoding="utf-8")
            text = f"I used plain DOM scripting. (MOCK)\n```html\n{html}\n```"
        return text, _tok(system + user), _tok(text)
