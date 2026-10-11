"""Gemini wrapper (google-genai): tokens, cost, backoff, concurrency cap.

Tokens are MEASURED from usage metadata. Dollars are COMPUTED from the PRICES dict (list price).
Pricing is marked ASSUMED until verified.
"""
import asyncio
import json
import re
from dataclasses import dataclass, field

import config

PRICES = {
    "pricing_date": "2026-10-11",
    "source": "Google's Gemini API pricing page (ai.google.dev/gemini-api/docs/pricing)",
    "models": {
        "gemini-3.5-flash-lite": {"input_per_m": 0.30, "output_per_m": 2.50},
        "mock-model": {"input_per_m": 0.30, "output_per_m": 2.50},
    },
}

RETRYABLE_CODES = {429, 503}
MAX_RETRIES = 5


class LLMError(Exception):
    pass


def price_for(model: str) -> tuple[float | None, float | None, bool]:
    m = PRICES.get("models", {}).get(model)
    if m is not None:
        return m["input_per_m"], m["output_per_m"], True
    return None, None, False


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    pin, pout, known = price_for(model)
    if not known or pin is None or pout is None:
        return None
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


@dataclass
class RunStats:
    """Accumulates tokens and cost by stage (plan, build, retry, autopsy)."""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    by_stage: dict = field(default_factory=dict)
    calls: int = 0

    def __post_init__(self):
        if self.model and not price_for(self.model)[2]:
            self.cost_usd = None

    def add(self, stage: str, input_tokens: int, output_tokens: int, cost: float | None):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if cost is None:
            self.cost_usd = None
        elif self.cost_usd is not None:
            self.cost_usd += cost
        self.calls += 1
        s = self.by_stage.setdefault(stage, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0})
        s["input_tokens"] += input_tokens
        s["output_tokens"] += output_tokens
        if cost is None:
            s["cost_usd"] = None
        elif s["cost_usd"] is not None:
            s["cost_usd"] += cost
        s["calls"] += 1

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost_by_stage(self) -> dict:
        return {
            k: (round(v["cost_usd"], 8) if v["cost_usd"] is not None else "UNPRICED")
            for k, v in self.by_stage.items()
        }

    @property
    def cost_display(self) -> str | float:
        if self.cost_usd is not None:
            return round(self.cost_usd, 8)
        return "UNPRICED"


def parse_json(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise LLMError(f"model did not return valid JSON: {t[:200]!r}")


class LLM:
    def __init__(self, model: str | None = None, client=None, temperature: float = 0.2,
                 concurrency: int = 2, sleep=asyncio.sleep):
        self.model = model or config.GEMINI_MODEL
        self.temperature = temperature
        self._client = client
        self._sem = asyncio.Semaphore(concurrency)
        self._sleep = sleep
        self.mock = False

    def _get_client(self):
        if self._client is None:
            if not config.GEMINI_API_KEY:
                raise LLMError("GEMINI_API_KEY is not set (copy .env.example to .env)")
            from google import genai
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client

    async def _raw(self, system: str, user: str, json_mode: bool) -> tuple[str, int, int]:
        """One API call. Returns (text, input_tokens, output_tokens). Overridden by MockLLM."""
        from google.genai import types
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            response_mime_type="application/json" if json_mode else None,
        )
        resp = await self._get_client().aio.models.generate_content(model=self.model, contents=user, config=cfg)
        u = resp.usage_metadata
        in_tok = int(getattr(u, "prompt_token_count", 0) or 0)
        # thinking tokens are billed as output
        out_tok = int(getattr(u, "candidates_token_count", 0) or 0) + int(getattr(u, "thoughts_token_count", 0) or 0)
        return (resp.text or ""), in_tok, out_tok

    async def _with_backoff(self, system, user, json_mode):
        delay = 1.0
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with self._sem:
                    return await self._raw(system, user, json_mode)
            except Exception as e:  # noqa: BLE001
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                if code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                    await self._sleep(delay)
                    delay *= 2
                    continue
                if isinstance(e, LLMError):
                    raise
                raise LLMError(f"Gemini call failed (code={code}): {e}") from e

    async def call(self, system: str, user: str, stage: str = "build", stats: RunStats | None = None) -> str:
        text, i, o = await self._with_backoff(system, user, json_mode=False)
        self._record(stats, stage, i, o)
        return text

    async def json_call(self, system: str, user: str, stage: str = "plan", stats: RunStats | None = None):
        text, i, o = await self._with_backoff(system, user, json_mode=True)
        self._record(stats, stage, i, o)
        return parse_json(text)

    def _record(self, stats, stage, i, o):
        if stats is not None:
            stats.model = self.model
            stats.add(stage, i, o, compute_cost(self.model, i, o))
