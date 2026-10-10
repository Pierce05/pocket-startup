import asyncio
from pathlib import Path

import pytest

from agent import checks, templates
from tests.conftest import needs_browser

FIX = Path(__file__).parent / "fixtures"
T1 = templates.get("tip_splitter")


@needs_browser
async def test_good_fixture_passes():
    r = await checks.run(T1, FIX / "good_tip.html")
    assert r.passed, (r.test, r.actual)


@needs_browser
async def test_bad_fixture_fails_on_zero_people():
    r = await checks.run(T1, FIX / "bad_tip.html")
    assert not r.passed
    assert r.test == "zero_people"


async def test_storage_usage_fails_without_browser(tmp_path):
    p = tmp_path / "index.html"
    p.write_text("<html><script>localStorage.setItem('a','b')</script></html>", encoding="utf-8")
    r = await checks.run(T1, p)
    assert not r.passed and r.test == "no_browser_storage"


async def test_session_storage_also_fails(tmp_path):
    p = tmp_path / "index.html"
    p.write_text("<script>sessionStorage.x=1</script>", encoding="utf-8")
    r = await checks.run(T1, p)
    assert r.test == "no_browser_storage"


async def test_hard_timeout(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(checks, "_run_sync", lambda *a, **k: time.sleep(1.5))
    p = tmp_path / "index.html"
    p.write_text("<html></html>", encoding="utf-8")
    r = await checks.run(T1, p, timeout_s=0.2)
    assert not r.passed and r.test == "timeout"


def test_result_dict_matches_retry_prompt_keys():
    from agent.prompts import RETRY_USER
    r = checks.Result(False, "t", "e", "a", ["boom"])
    assert "boom" in RETRY_USER.format(**r.as_dict())
