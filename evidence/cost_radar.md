# Pocket Startup: A/B Experiment & Cost Radar Report

> **Evaluation:** Baseline (`BUILDER_SYSTEM_V1`) vs Improved (`BUILDER_SYSTEM_V1` + Frozen Candidate B Patch)
> **Status:** Autopsy disabled (`autopsy=False`), Playwright acceptance checks, sequential execution.

## 1. Experiment Configuration & Metadata

- **Model:** `gemini-3.5-flash-lite` `[CONFIG]`
- **Temperature:** `0.2` `[CONFIG]`
- **Pricing Date & Source:** `2026-10-11` (Google's Gemini API pricing page (ai.google.dev/gemini-api/docs/pricing)) `[CONFIG]`
- **Ideas per Set:** `5` `[CONFIG]`
- **Repeats per Idea:** `2` `[CONFIG]`
- **Generated At:** `2026-10-11T07:40:20.349946+00:00` `[MEASURED]`
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
| Total runs (N) | `[MEASURED]` | 10 | 10 | - |
| First-attempt passes | `[MEASURED]` | 0/10 (0.0%) | 10/10 (100.0%) | +100.0% |
| Eventual successes | `[MEASURED]` | 9/10 (90.0%) | 10/10 (100.0%) | +10.0% |
| Avg attempts per run | `[MEASURED]` | 2.60 | 1.00 | -1.60 |
| Total tokens | `[MEASURED]` | 118,307 | 25,921 | -92,386 |
| Avg tokens per run | `[MEASURED]` | 11,830.7 | 2,592.1 | -9,238.6 |
| Total cost | `[COMPUTED]` | $0.182351 | $0.053963 | $-0.128388 |
| Cost per success | `[COMPUTED]` | $0.020261 | $0.005396 | $-0.014865 (-73.4%) |
| Retry tax | `[COMPUTED]` | 63.37% | 0.00% | -63.37% |
| Median latency | `[MEASURED]` | 19.38s | 9.38s | -10.01s |

### Cohort 2: Held-Out Set (Genuinely Unseen)

| Metric | Tag | Baseline | Improved | Delta / Impact |
| :--- | :---: | :---: | :---: | :---: |
| Ideas evaluated | `[MEASURED]` | 5 | 5 | Identical cohort |
| Total runs (N) | `[MEASURED]` | 10 | 10 | - |
| First-attempt passes | `[MEASURED]` | 2/10 (20.0%) | 8/10 (80.0%) | +60.0% |
| Eventual successes | `[MEASURED]` | 9/10 (90.0%) | 9/10 (90.0%) | +0.0% |
| Avg attempts per run | `[MEASURED]` | 2.30 | 1.50 | -0.80 |
| Total tokens | `[MEASURED]` | 105,531 | 48,152 | -57,379 |
| Avg tokens per run | `[MEASURED]` | 10,553.1 | 4,815.2 | -5,737.9 |
| Total cost | `[COMPUTED]` | $0.167806 | $0.083805 | $-0.084001 |
| Cost per success | `[COMPUTED]` | $0.018645 | $0.009312 | $-0.009333 (-50.1%) |
| Retry tax | `[COMPUTED]` | 58.88% | 32.08% | -26.80% |
| Median latency | `[MEASURED]` | 20.21s | 9.60s | -10.61s |

### Combined Overall Totals

| Metric | Tag | Baseline | Improved | Delta / Impact |
| :--- | :---: | :---: | :---: | :---: |
| Ideas evaluated | `[MEASURED]` | 10 | 10 | Identical cohort |
| Total runs (N) | `[MEASURED]` | 20 | 20 | - |
| First-attempt passes | `[MEASURED]` | 2/20 (10.0%) | 18/20 (90.0%) | +80.0% |
| Eventual successes | `[MEASURED]` | 18/20 (90.0%) | 19/20 (95.0%) | +5.0% |
| Avg attempts per run | `[MEASURED]` | 2.45 | 1.25 | -1.20 |
| Total tokens | `[MEASURED]` | 223,838 | 74,073 | -149,765 |
| Avg tokens per run | `[MEASURED]` | 11,191.9 | 3,703.7 | -7,488.2 |
| Total cost | `[COMPUTED]` | $0.350157 | $0.137768 | $-0.212389 |
| Cost per success | `[COMPUTED]` | $0.019453 | $0.007251 | $-0.012202 (-62.7%) |
| Retry tax | `[COMPUTED]` | 61.22% | 19.52% | -41.70% |
| Median latency | `[MEASURED]` | 20.09s | 9.48s | -10.60s |

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