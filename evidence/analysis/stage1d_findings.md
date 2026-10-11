# Stage 1d Investigation Findings: Run `20261011-035932-b372`

**Date:** 2026-10-11  
**Target Run:** `evidence/runs/20261011-035932-b372` (Mode: baseline, Template: tip_splitter)

---

## 1. Emptiness Measurement of `#result` in `agent/checks.py`

### Finding
In `agent/checks.py` (prior to Stage 1d fixes):
- Line 54: `def _text(page, sel) -> str: return page.inner_text(sel).strip()`
- Line 71-76:
  ```python
  def _expect_invalid(page, url, test, bill, people, tip):
      _tip_case(page, url, bill, people, tip)
      visible, res = _err_visible(page), _text(page, "#result")
      if not visible or res:
          raise _Fail(test, "#error visible with a message and #result empty",
                      f"#error visible={visible}, #result={res!r}")
  ```

### Analysis
- Emptiness was evaluated strictly by whether `_text(page, "#result")` returned a non-empty string.
- In `attempt_1.html`, when invalid input was provided (bill 100, people 0, tip 20), the application set `#error` to visible and hid `#result` via CSS (`display: none`). However, `#result` still retained text content in the DOM.
- Because `_expect_invalid` did not evaluate whether `#result` was visible to the user (`page.is_visible("#result")`), it treated DOM text inside a hidden element as a test failure (`zero_people`).
- To a human user, the error was clearly visible and no result was displayed. Judging pass/fail by hidden DOM text penalized visually correct applications.

---

## 2. Retry Payload & Context Amnesia in `agent/loop.py` and `agent/prompts.py`

### Finding
In `agent/loop.py` (prior to Stage 1d fixes):
- Line 143:
  ```python
  if attempt < rails.max_attempts:
      feedback = prompts.RETRY_USER.format(**result.as_dict())
      _emit("retry", {"next": attempt + 1})
  ```
- In `agent/prompts.py`:
  ```python
  RETRY_USER = """Your previous attempt failed automated checks.
  Failed test: {test_name}
  Expected: {expected}
  Actual: {actual}
  Browser console errors: {console_errors}
  Fix the root cause. Do not rewrite unrelated parts. Return the complete corrected index.html in one html code block, preceded by one sentence naming the root cause."""
  ```

### Analysis
- The retry prompt transmitted **only** the test failure fields: `{test_name}`, `{expected}`, `{actual}`, and `{console_errors}`.
- It did **not** transmit:
  - Product specification (`spec_json`)
  - Required element IDs (`ids`)
  - Template notes (`template_notes`)
  - The previous attempt's generated HTML (`previous_html`)
- Because the model received no context about the application it had just built or the required IDs, it suffered complete context amnesia across attempts:
  - **Attempt 1:** Tip Splitter with all required IDs (`#bill`, `#people`, `#tip`, `#calc`, `#result`, `#error`). Visibly working, failed on hidden `#result` text check.
  - **Attempt 2:** Re-implemented from scratch without `#calc`, causing Playwright action timeouts.
  - **Attempt 3:** Hallucinated a generic math calculator (`#display`, `#history`).
  - **Attempt 4:** Hallucinated a retail point-of-sale checkout system.

---

## 3. Implemented Remediation

1. **Acceptance Checks (`agent/checks.py`):**
   - Refactored `_expect_invalid` to judge by user visibility: passes when `#error` is visible with text and `#result` is either not visible OR visible with empty text. Fails when `#result` is visible with content.
   - Added pre-flight `required_ids` check that verifies all required template IDs exist on page load before scripted interactions, failing with named test `"required_ids"` and listing missing IDs.
   - Reduced `ACTION_TIMEOUT_MS` to 3,000 ms (~3 s). Wrapped scripted interaction steps in named `_step` blocks so Playwright runtime errors produce named test failures with `expected` and `actual` filled in instead of generic `check_error`.

2. **Retry Pipeline (`agent/prompts.py`, `agent/loop.py`):**
   - Enriched `RETRY_USER` to include the full product spec, required element IDs, template notes, the previous attempt's HTML, and structured failure details.
   - Instructed the model to keep every required element ID and change only what is needed, without adding test-specific hints.

3. **Evidence Isolation:**
   - Pre-fix runs (including Gate G1 run `20261011-035932-b372`) are preserved in `evidence/runs/` as evidence of prompt drift and check semantics, but recorded as excluded from A/B statistical comparisons in `evidence/CHECK_CHANGELOG.md`.
