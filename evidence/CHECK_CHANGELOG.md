# Acceptance Check Changelog

## 2026-10-11: Stage 1d Acceptance Check Semantics & Retry Context Fixes

### 1. Judge `#result` by User Visibility (`agent/checks.py`)
- **Change:** In invalid-input tests (`_expect_invalid`), test passes when `#error` is visible with non-empty text AND `#result` is either not visible (`is_visible("#result") == False`) OR visible with empty text (`inner_text("#result").strip() == ""`). It fails when `#result` is visible with content.
- **Reason:** Previous implementation checked `_text(page, "#result")` directly. In Chromium, an element hidden via CSS (`display: none`) can still retain text in the DOM, causing `inner_text` / DOM queries to see text even though a human user sees an empty/hidden result. Acceptance checks must judge what the user actually sees on screen.
- **Verification Fixtures:**
  - `tests/fixtures/hidden_result_with_text.html`: `#result` hidden via `display: none` but retaining text -> PASSES.
  - `tests/fixtures/visible_zero_result.html`: `#result` visible showing `$0.00` -> FAILS on `zero_people`.

### 2. Pre-flight `required_ids` Check (`agent/checks.py`)
- **Change:** Before executing scripted user interactions, `_run_sync` verifies that every required element ID (selectors starting with `#` in `tpl.ids`) exists in the DOM. If any are missing, the check fails immediately with test name `"required_ids"` and lists the missing IDs in `actual`.
- **Reason:** In run `20261011-035932-b372`, attempt 2 drifted and omitted `#calc`, which caused unhandled Playwright action timeouts. Pre-flight ID verification fails fast with an explicit, structured list of missing IDs that guides the model on retry.

### 3. Action Timeouts and Scripted Step Error Mapping (`agent/checks.py`)
- **Change:** Shortened `ACTION_TIMEOUT_MS` from 5,000 ms to 3,000 ms (~3 s), well within the overall 15 s check timeout (`CHECK_TIMEOUT_S`). Scripted steps are wrapped in named step contexts (`_step`); any Playwright runtime errors or action timeouts during a scripted interaction now produce a named test failure with `test`, `expected`, and `actual` filled in instead of a generic `"check_error"`.
- **Reason:** Prevents runs from hanging on individual element actions and ensures error feedback to the model and autopsy report clearly identifies which test and action failed.

### 4. Retry Context Preservation (`agent/prompts.py`, `agent/loop.py`)
- **Change:** `RETRY_USER` and `run_build()` retry dispatch now provide the complete product specification (`spec_json`), required element IDs (`ids`), template notes (`template_notes`), the previous attempt's full HTML (`previous_html`), and the structured check failure (`test_name`, `expected`, `actual`, `console_errors`). The prompt instructs the model to keep every required element ID and change only what is needed, with no test-specific hints.
- **Reason:** In run `20261011-035932-b372`, attempts 2, 3, and 4 experienced catastrophic context amnesia because the retry prompt previously omitted the product spec, required IDs, template notes, and previous code. The model drifted into unrelated applications (a generic calculator, then a POS app). Preserving full context keeps the model anchored to the spec and its prior code.

---

## Statistical Exclusion Notice for Earlier Runs
All runs executed before this changelog (including Gate G1 smoke runs such as `20261011-035932-b372`):
- **Retained as Evidence:** The run artifacts (`result.json`, `events.json`, `index.html`, `attempt_*.html`, `autopsy.json`) are preserved under `evidence/runs/` as permanent records of system behavior, check semantics, and drift patterns.
- **Excluded from A/B Statistics:** Because these runs were evaluated under the pre-fix check semantics (hidden DOM text counted as non-empty result) and experienced stateless retry drift, they MUST be excluded from all baseline and improved A/B statistical comparisons.

---

## 2026-10-11 10:05 IST: Stage 1e Spec-Derived Acceptance Suite Hardening

### 1. Spec Extension in Template Notes (`agent/templates.py`)
- **Change:** Extended `tip_splitter` template notes with general sentences only:
  > "Invalid input (anything for which a per-person amount cannot be meaningfully computed) must show a message in #error and leave #result empty or hidden. Valid input must show the per-person amount in #result with two decimals and hide #error."
- **Reason:** Every acceptance check must trace directly to a specification sentence in the template notes, without listing specific edge cases or secretly making the spec harder than what a careful human reviewer expects.

### 2. Broadened Playwright Acceptance Suite (`agent/checks.py`)
- **Change:** Expanded `check_tip_splitter` to cover:
  - **Invalid inputs:** empty bill (`blank_bill`), negative bill (`negative_bill`), negative tip (`negative_tip`), zero people (`zero_people`), negative people (`negative_people`), fractional people (`fractional_people`, e.g. 2.5), and non-numeric bill (`non_numeric_bill`).
  - **Valid inputs:** basic split (`split_basic`: 100 / 4 / 20 -> 30.00), zero tip fractional (`split_zero_tip_fractional`: 100 / 3 / 0 -> 33.33), valid after invalid (`invalid_then_valid`: invalid calculation followed by valid calculation hides #error and shows correct #result), and consecutive valid updates (`two_valid_in_a_row`: sequential valid calculations update #result).
  - Added helper `_expect_valid` ensuring valid calculations show the two-decimal amount in `#result`, `#result` is visible, and `#error` is hidden.
- **Reason:** Hardens the acceptance suite against common arithmetic edge cases (fractional and negative denominators) and ensures state transitions (invalid-to-valid and valid-to-valid) update DOM state cleanly.

### 3. Fixtures for New Invalid Cases (`tests/fixtures/`)
- **Fixtures added:**
  - `bad_negative_bill.html`: omits negative bill check (verifies failure on `negative_bill`).
  - `bad_negative_people.html`: checks only `people === 0` (verifies failure on `negative_people`).
  - `bad_fractional_people.html`: omits integer check (verifies failure on `fractional_people`).
- **Good fixture verification:** Confirmed that `tests/fixtures/good_tip.html` passes all new and existing tests in the suite.

### 4. Statistical Exclusion Notice
All runs executed before this change (including Gate G1 runs and any runs prior to 2026-10-11 10:05 IST):
- **Retained as Evidence:** Run artifacts remain in `evidence/runs/`.
- **Excluded from A/B Statistics:** Excluded from A/B metrics because they were evaluated against the narrower acceptance suite before Stage 1e hardening.
