"""Acceptance checks. Pass/fail is decided here, in code, never by an LLM.

Sync Playwright runs in a worker thread (asyncio.to_thread). Network is blocked, everything except file://
is aborted, and the whole check is wrapped in a hard 15 second timeout.
"""
import asyncio
from contextlib import contextmanager
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

import config
from agent import templates

STORAGE_RE = re.compile(r"\b(localStorage|sessionStorage)\b")
ACTION_TIMEOUT_MS = 3_000

_tls = threading.local()


@dataclass
class Result:
    passed: bool
    test: str = ""
    expected: str = ""
    actual: str = ""
    console_errors: list = field(default_factory=list)

    def as_dict(self) -> dict:
        """Keys match RETRY_USER placeholders."""
        return {
            "test_name": self.test,
            "expected": self.expected,
            "actual": self.actual,
            "console_errors": "; ".join(self.console_errors) or "none",
            "spec_json": "{}",
            "ids": "",
            "template_notes": "",
            "previous_html": "",
        }


class _Fail(Exception):
    def __init__(self, test, expected, actual):
        self.test, self.expected, self.actual = test, expected, actual


@contextmanager
def _step(name: str, expected: str = "step completes without error"):
    old = getattr(_tls, "current", ("setup", "setup completes"))
    _tls.current = (name, expected)
    try:
        yield
    finally:
        _tls.current = old


def _set(page, sel, val):
    page.evaluate(
        "([s, v]) => { const e = document.querySelector(s); if (!e) throw new Error('missing ' + s); "
        "e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); "
        "e.dispatchEvent(new Event('change', {bubbles: true})); }",
        [sel, str(val)],
    )


def _click(page, sel):
    page.click(sel)
    page.wait_for_timeout(60)


def _text(page, sel) -> str:
    return page.inner_text(sel).strip()


def _err_visible(page) -> bool:
    return page.is_visible("#error") and bool(_text(page, "#error"))


def _res_visible_content(page) -> str:
    if not page.is_visible("#result"):
        return ""
    return page.inner_text("#result").strip()


# ---- T1 Tip Splitter ---------------------------------------------------------------------------------
def _tip_case(page, url, bill, people, tip):
    page.goto(url)
    _set(page, "#bill", bill)
    _set(page, "#people", people)
    _set(page, "#tip", tip)
    _click(page, "#calc")


def _expect_invalid(page, url, test, bill, people, tip):
    _tip_case(page, url, bill, people, tip)
    err_ok = _err_visible(page)
    res_content = _res_visible_content(page)
    if not err_ok or res_content:
        raise _Fail(
            test,
            "#error visible with a message and #result not visible or empty",
            f"#error visible={err_ok}, #result visible_content={res_content!r}",
        )


def check_tip_splitter(page, url):
    with _step("split_basic", "#result contains 30.00 (bill 100, 4 people, 20% tip)"):
        _tip_case(page, url, 100, 4, 20)
        got = _text(page, "#result")
        if "30.00" not in got:
            raise _Fail("split_basic", "#result contains 30.00 (bill 100, 4 people, 20% tip)", f"#result={got!r}")

    with _step("zero_people", "#error visible with message and #result not visible or empty"):
        _expect_invalid(page, url, "zero_people", 100, 0, 20)

    with _step("negative_tip", "#error visible with message and #result not visible or empty"):
        _expect_invalid(page, url, "negative_tip", 100, 4, -5)

    with _step("blank_bill", "#error visible with message and #result not visible or empty"):
        _expect_invalid(page, url, "blank_bill", "", 4, 10)

    with _step("non_numeric_bill", "#error visible with message and #result not visible or empty"):
        _expect_invalid(page, url, "non_numeric_bill", "abc", 4, 10)


# ---- T2 Habit Tracker --------------------------------------------------------------------------------
def check_habit_tracker(page, url):
    with _step("add_two_habits", ".habit count is 2 after adding Read and Walk"):
        page.goto(url)
        for name in ("Read", "Walk"):
            _set(page, "#habit-input", name)
            _click(page, "#add")
        n = page.locator(".habit").count()
        if n != 2:
            raise _Fail("add_two_habits", ".habit count is 2 after adding Read and Walk", f"count={n}")

    with _step("streak_after_done", "#streak shows 1 after marking one habit done"):
        btn = page.locator(".habit .done-btn")
        (btn.first if btn.count() else page.locator(".done-btn").first).click()
        page.wait_for_timeout(60)
        streak = _text(page, "#streak")
        if "1" not in streak:
            raise _Fail("streak_after_done", "#streak shows 1 after marking one habit done", f"#streak={streak!r}")

    with _step("empty_add_rejected", ".habit count stays 2 when adding an empty habit"):
        _set(page, "#habit-input", "")
        _click(page, "#add")
        n = page.locator(".habit").count()
        if n != 2:
            raise _Fail("empty_add_rejected", ".habit count stays 2 when adding an empty habit", f"count={n}")


# ---- T3 Flashcards -----------------------------------------------------------------------------------
def check_flashcards(page, url):
    with _step("next_changes_card", "#card-view changes after #next"):
        page.goto(url)
        for f, b in (("Q1", "A1"), ("Q2", "A2")):
            _set(page, "#front", f)
            _set(page, "#back", b)
            _click(page, "#add-card")
        before = _text(page, "#card-view")
        _click(page, "#next")
        after = _text(page, "#card-view")
        if before == after:
            raise _Fail("next_changes_card", "#card-view changes after #next", f"before={before!r}, after={after!r}")

    with _step("flip_shows_back", "#card-view shows the back text (A1 or A2) after #flip"):
        _click(page, "#flip")
        flipped = _text(page, "#card-view")
        if not any(a in flipped for a in ("A1", "A2")):
            raise _Fail("flip_shows_back", "#card-view shows the back text (A1 or A2) after #flip", f"#card-view={flipped!r}")


TEMPLATE_CHECKS = {
    "tip_splitter": check_tip_splitter,
    "habit_tracker": check_habit_tracker,
    "flashcards": check_flashcards,
}


def _run_sync(template_name: str, path) -> Result:
    html = Path(path).read_text(encoding="utf-8", errors="ignore")
    if STORAGE_RE.search(html):
        return Result(False, "no_browser_storage", "no localStorage or sessionStorage usage",
                      "the HTML references localStorage or sessionStorage")
    tpl = templates.get(template_name)
    required_ids = [sel for sel in tpl.ids if sel.startswith("#")]
    errors: list[str] = []
    _tls.current = ("setup", "browser environment initialises")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(offline=True)
                ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file://") else r.abort())
                page = ctx.new_page()
                page.set_default_timeout(ACTION_TIMEOUT_MS)
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                url = Path(path).resolve().as_uri()

                # Pre-flight check: required element ids
                with _step("required_ids", f"all required ids present: {', '.join(required_ids)}"):
                    page.goto(url)
                    missing = [sel for sel in required_ids if page.locator(sel).count() == 0]
                    if missing:
                        raise _Fail(
                            "required_ids",
                            f"all required ids present: {', '.join(required_ids)}",
                            f"missing: {', '.join(missing)}",
                        )

                TEMPLATE_CHECKS[template_name](page, url)
            finally:
                browser.close()
    except _Fail as f:
        return Result(False, f.test, f.expected, f.actual, errors)
    except Exception as e:  # noqa: BLE001
        cur_test, cur_exp = getattr(_tls, "current", ("check_error", "the check completes"))
        return Result(False, cur_test, cur_exp, f"{type(e).__name__}: {str(e)[:300]}", errors)
    return Result(True, console_errors=errors)


async def run(template, path, timeout_s: float | None = None) -> Result:
    """`template` is a Template (or a template name). Hard timeout around the whole check."""
    name = getattr(template, "name", template)
    limit = timeout_s or config.CHECK_TIMEOUT_S
    try:
        return await asyncio.wait_for(asyncio.to_thread(_run_sync, name, path), timeout=limit)
    except asyncio.TimeoutError:
        return Result(False, "timeout", f"check finishes within {limit}s", f"check exceeded {limit}s")
