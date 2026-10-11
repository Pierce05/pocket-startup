import json
from types import SimpleNamespace

import pytest

from agent import llm as L


class FakeErr(Exception):
    def __init__(self, code):
        super().__init__(f"http {code}")
        self.code = code


def fake_client(responses):
    calls = {"n": 0}

    async def generate_content(model, contents, config):
        r = responses[calls["n"]]
        calls["n"] += 1
        if isinstance(r, Exception):
            raise r
        return r

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    return client, calls


def resp(text, p=100, c=40, t=10):
    return SimpleNamespace(text=text, usage_metadata=SimpleNamespace(
        prompt_token_count=p, candidates_token_count=c, thoughts_token_count=t))


async def no_sleep(_):
    return None


async def test_tokens_and_cost_recorded_by_stage():
    client, _ = fake_client([resp("hello", 1000, 200, 50)])
    llm = L.LLM(model="gemini-3.5-flash-lite", client=client, sleep=no_sleep)
    stats = L.RunStats()
    assert await llm.call("s", "u", stage="build", stats=stats) == "hello"
    assert stats.input_tokens == 1000 and stats.output_tokens == 250  # thinking tokens counted as output
    expected = (1000 * 0.30 + 250 * 2.50) / 1e6
    assert stats.cost_usd == pytest.approx(expected)
    assert stats.cost_by_stage() == {"build": pytest.approx(expected)}
    assert stats.cost_display == round(expected, 8)


async def test_unpriced_model_records_unpriced_cost():
    client, _ = fake_client([resp("hello", 1000, 200, 50)])
    llm = L.LLM(model="unknown-custom-model", client=client, sleep=no_sleep)
    stats = L.RunStats()
    assert await llm.call("s", "u", stage="build", stats=stats) == "hello"
    assert stats.input_tokens == 1000 and stats.output_tokens == 250
    assert stats.cost_usd is None
    assert stats.cost_display == "UNPRICED"
    assert stats.cost_by_stage() == {"build": "UNPRICED"}
    assert L.compute_cost("unknown-custom-model", 1000, 250) is None


async def test_backoff_retries_429_and_503_then_succeeds():
    client, calls = fake_client([FakeErr(429), FakeErr(503), resp("ok")])
    llm = L.LLM(client=client, sleep=no_sleep)
    assert await llm.call("s", "u") == "ok"
    assert calls["n"] == 3


async def test_non_retryable_error_raises_llmerror():
    client, calls = fake_client([FakeErr(400)])
    llm = L.LLM(client=client, sleep=no_sleep)
    with pytest.raises(L.LLMError):
        await llm.call("s", "u")
    assert calls["n"] == 1


async def test_gives_up_after_max_retries():
    client, calls = fake_client([FakeErr(429)] * (L.MAX_RETRIES + 1))
    llm = L.LLM(client=client, sleep=no_sleep)
    with pytest.raises(L.LLMError):
        await llm.call("s", "u")
    assert calls["n"] == L.MAX_RETRIES + 1


async def test_json_call_strips_fences():
    client, _ = fake_client([resp('```json\n{"a": 1}\n```')])
    llm = L.LLM(client=client, sleep=no_sleep)
    assert await llm.json_call("s", "u") == {"a": 1}


def test_parse_json_rejects_garbage():
    with pytest.raises(L.LLMError):
        L.parse_json("not json at all")


def test_concurrency_cap_is_two():
    assert L.LLM(client=object())._sem._value == 2


def test_pricing_has_date_field_and_flags_unknown_models():
    assert L.PRICES["pricing_date"] == "2026-10-11"
    assert "ai.google.dev/gemini-api/docs/pricing" in L.PRICES["source"]
    assert "gemini-3.5-flash-lite" in L.PRICES["models"]
    assert "mock-model" in L.PRICES["models"]
    assert "gemini-2.5-flash" not in L.PRICES["models"]

    pin, pout, known = L.price_for("gemini-3.5-flash-lite")
    assert known is True
    assert pin == 0.30
    assert pout == 2.50

    # gemini-2.5-flash is removed and unpriced
    pin_25, pout_25, known_25 = L.price_for("gemini-2.5-flash")
    assert known_25 is False
    assert pin_25 is None
    assert pout_25 is None
    assert L.compute_cost("gemini-2.5-flash", 1000, 200) is None

    # Unpriced model does NOT fall back
    pin_u, pout_u, known_u = L.price_for("some-new-model")
    assert known_u is False
    assert pin_u is None
    assert pout_u is None
