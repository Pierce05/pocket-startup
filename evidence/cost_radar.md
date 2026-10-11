# Pocket Startup: A/B Experiment & Cost Radar Report

> **Evaluation:** Baseline (`BUILDER_SYSTEM_V1`) vs Improved (`BUILDER_SYSTEM_V1` + Frozen Candidate B Patch)
> **Status:** Autopsy disabled (`autopsy=False`), Playwright acceptance checks, sequential execution.

## 1. Experiment Configuration & Metadata

- **Model:** `gemini-3.5-flash-lite` `[CONFIG]`
- **Temperature:** `0.2` `[CONFIG]`
- **Pricing Date & Source:** `2026-10-11` (Google's Gemini API pricing page (ai.google.dev/gemini-api/docs/pricing)) `[CONFIG]`
- **Ideas per Set:** `5` `[CONFIG]`
- **Repeats per Idea:** `4` `[CONFIG]`
- **Generated At:** `2026-10-11T09:15:38.121197+00:00` `[MEASURED]`
- **Frozen Winner Patch (SHA-256):** `49156a5318072806...` `[CONFIG]`

### Frozen Winner Patch Text
```text
Before performing any calculation, check every numeric input. Verify that the bill is zero or greater, the tip percentage is zero or greater, and the number of people is a whole number greater than zero. On any invalid input, show an error message in #error and do not display anything in #result.
```

---

## 2. A/B Performance Summary

### Cohort 1: Tuning Set (Seen Failures)

| Metric | Tag | Baseline | Improved | Delta / Impact |
| :--- | :---: | :---: | :---: | :---: |
| Ideas evaluated | `[MEASURED]` | 5 | 5 | Identical cohort |
| Total runs (N) | `[MEASURED]` | 20 | 20 | - |
| First-attempt passes | `[MEASURED]` | 1/20 (5.0%) [CI95: 0.9%–23.6%] | 20/20 (100.0%) [CI95: 83.9%–100.0%] | +95.0% |
| Fisher exact test (first-pass) | `[COMPUTED]` | n = 20 | n = 20 |  (p < 0.001) |
| Eventual successes | `[MEASURED]` | 20/20 (100.0%) | 20/20 (100.0%) | +0.0% |
| Failures by test name | `[MEASURED]` | fractional_people: 19 | None | - |
| Avg attempts per run | `[MEASURED]` | 2.00 | 1.00 | -1.00 |
| Input tokens (total / avg) | `[MEASURED]` | 59,215 (2,960.8/run) | 8,896 (444.8/run) | -50,319 (-2,516.0/run) |
| Output tokens (total / avg) | `[MEASURED]` | 89,319 (4,465.9/run) | 42,174 (2,108.7/run) | -47,145 (-2,357.2/run) |
| Total tokens (in + out) | `[MEASURED]` | 148,534 (7,426.7/run) | 51,070 (2,553.5/run) | -97,464 (-4,873.2/run) |
| Total cost | `[COMPUTED]` | $0.241062 | $0.108104 | $-0.132958 |
| Cost per success | `[COMPUTED]` | $0.012053 | $0.005405 | $-0.006648 (-55.2%) |
| Retry tax (incl. autopsy) | `[COMPUTED]` | 51.60% | 0.00% | -51.60% |
| Retry tax (excl. autopsy) | `[COMPUTED]` | 51.60% | 0.00% | -51.60% |
| Median latency | `[MEASURED]` | 17.48s | 10.07s | -7.41s |

### Cohort 2: Held-Out Set (Genuinely Unseen)

| Metric | Tag | Baseline | Improved | Delta / Impact |
| :--- | :---: | :---: | :---: | :---: |
| Ideas evaluated | `[MEASURED]` | 5 | 5 | Identical cohort |
| Total runs (N) | `[MEASURED]` | 20 | 20 | - |
| First-attempt passes | `[MEASURED]` | 1/20 (5.0%) [CI95: 0.9%–23.6%] | 16/20 (80.0%) [CI95: 58.4%–91.9%] | +75.0% |
| Fisher exact test (first-pass) | `[COMPUTED]` | n = 20 | n = 20 |  (p < 0.001) |
| Eventual successes | `[MEASURED]` | 15/20 (75.0%) | 19/20 (95.0%) | +20.0% |
| Failures by test name | `[MEASURED]` | fractional_people: 14, split_basic: 5 | split_basic: 4 | - |
| Avg attempts per run | `[MEASURED]` | 2.60 | 1.45 | -1.15 |
| Input tokens (total / avg) | `[MEASURED]` | 95,255 (4,762.8/run) | 29,643 (1,482.2/run) | -65,612 (-3,280.6/run) |
| Output tokens (total / avg) | `[MEASURED]` | 127,459 (6,372.9/run) | 60,262 (3,013.1/run) | -67,197 (-3,359.8/run) |
| Total tokens (in + out) | `[MEASURED]` | 222,714 (11,135.7/run) | 89,905 (4,495.2/run) | -132,809 (-6,640.5/run) |
| Total cost | `[COMPUTED]` | $0.347224 | $0.159548 | $-0.187676 |
| Cost per success | `[COMPUTED]` | $0.023148 | $0.008397 | $-0.014751 (-63.7%) |
| Retry tax (incl. autopsy) | `[COMPUTED]` | 62.90% | 30.76% | -32.14% |
| Retry tax (excl. autopsy) | `[COMPUTED]` | 62.90% | 30.76% | -32.14% |
| Median latency | `[MEASURED]` | 20.55s | 10.68s | -9.87s |

### Combined Overall Totals

| Metric | Tag | Baseline | Improved | Delta / Impact |
| :--- | :---: | :---: | :---: | :---: |
| Ideas evaluated | `[MEASURED]` | 10 | 10 | Identical cohort |
| Total runs (N) | `[MEASURED]` | 40 | 40 | - |
| First-attempt passes | `[MEASURED]` | 2/40 (5.0%) [CI95: 1.4%–16.5%] | 36/40 (90.0%) [CI95: 77.0%–96.0%] | +85.0% |
| Fisher exact test (first-pass) | `[COMPUTED]` | n = 40 | n = 40 |  (p < 0.001) |
| Eventual successes | `[MEASURED]` | 35/40 (87.5%) | 39/40 (97.5%) | +10.0% |
| Failures by test name | `[MEASURED]` | fractional_people: 33, split_basic: 5 | split_basic: 4 | - |
| Avg attempts per run | `[MEASURED]` | 2.30 | 1.23 | -1.07 |
| Input tokens (total / avg) | `[MEASURED]` | 154,470 (3,861.8/run) | 38,539 (963.5/run) | -115,931 (-2,898.3/run) |
| Output tokens (total / avg) | `[MEASURED]` | 216,778 (5,419.4/run) | 102,436 (2,560.9/run) | -114,342 (-2,858.5/run) |
| Total tokens (in + out) | `[MEASURED]` | 371,248 (9,281.2/run) | 140,975 (3,524.4/run) | -230,273 (-5,756.8/run) |
| Total cost | `[COMPUTED]` | $0.588286 | $0.267652 | $-0.320634 |
| Cost per success | `[COMPUTED]` | $0.016808 | $0.006863 | $-0.009945 (-59.2%) |
| Retry tax (incl. autopsy) | `[COMPUTED]` | 58.27% | 18.33% | -39.94% |
| Retry tax (excl. autopsy) | `[COMPUTED]` | 58.27% | 18.33% | -39.94% |
| Median latency | `[MEASURED]` | 18.98s | 10.22s | -8.77s |

---

## 3. Cost Radar Formulas & Definitions

1. **Cost per Success (`[COMPUTED]`):**
   $$\text{Cost per Success} = \frac{\sum \text{Cost of ALL Runs}}{\text{Count of Successful Runs}}$$
   - Accounts for the financial waste of failing runs and retries.
   - If successes = 0, the metric is reported as `None` / `N/A` (zero-success edge case handled cleanly without division by zero).

2. **Retry Tax (`[COMPUTED]`):**
   $$\text{Retry Tax} = \frac{\text{Cost Incurred After First Build}}{\text{Total Cost}} = \frac{\text{Cost}(\text{retry}) + \text{Cost}(\text{autopsy})}{\text{Total Cost}}$$
   - During this A/B experiment, `autopsy=False`, so Retry Tax isolates the cost spent on retrying attempts 2..4.
   - If total cost = $0.00, Retry Tax defaults to 0.0% without division error.

3. **First-Attempt Pass Rate (`[MEASURED]`):**
   $$\text{First-Attempt Pass Rate} = \frac{\text{Runs Passing on Attempt 1}}{\text{Total Runs}}$$
   - Decisive metric for eliminating latency and token overhead.

---

## 4. Measurement & Audit Trail

- **Pass/Fail Authority:** Deterministic Playwright headless Chromium runner.
- **Autopsy Execution:** Disabled (`autopsy=False`) across both baseline and improved arms.
- **Candidate Exclusions:** `candidate_a` and `candidate_b` patch-lab runs are excluded from standard A/B aggregates.
- **Failure Preservation:** Failed runs are permanently preserved in `evidence/runs/`.