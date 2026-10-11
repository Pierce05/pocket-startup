# Post-1e Baseline Failure Clusters & Prompt Synthesis

**Date:** 2026-10-11  
**Dataset:** 10 Post-Stage 1e Baseline Runs (`20261011-043610-3f24` through `20261011-043923-413e`)  
**Scope:** Tuning-set ideas only (`experiments/ideas.py`). Held-out ideas are strictly excluded.

---

## 1. Summary of First-Attempt Outcomes

Across the 10 post-1e baseline runs on the tuning set:
- **Total runs:** 10
- **Passed first attempt:** 1 (Run `20261011-043752-241f`)
- **Failed first attempt:** 9 (90% first-attempt failure rate, creating 53.0% retry tax)
- **Final success after retry:** 10 / 10 (100% final success rate)

---

## 2. Inventory of First-Attempt Failures

| Run ID | Idea | Failed Check | Autopsy Root Cause Summary |
|---|---|---|---|
| `20261011-043610-3f24` | Tip splitter for friends | `fractional_people` | Allowed fractional people count; calculated result instead of showing `#error`. |
| `20261011-043633-7471` | Shared grocery receipt | `fractional_people` | Missing whole-number check for people count; allowed fractional calculation. |
| `20261011-043653-35f6` | Bar tab splitter | `fractional_people` | People input not validated as positive integer; calculated instead of error. |
| `20261011-043715-d673` | Taxi fare splitter | `fractional_people` | Passenger count not checked for integer; computed result on fractional input. |
| `20261011-043734-40b9` | Wedding dinner bill splitter | `fractional_people` | Guest count integer check omitted; calculated result on fractional input. |
| `20261011-043802-a36c` | Shared grocery receipt | `fractional_people` | Missing `Number.isInteger()` check on roommate count; result computed. |
| `20261011-043821-632d` | Bar tab splitter | `fractional_people` | Integer validation for people field missing/truncated; result computed. |
| `20261011-043853-7760` | Taxi fare splitter | `fractional_people` | Failed to detect non-integer passenger values; calculated instead of `#error`. |
| `20261011-043923-413e` | Wedding dinner bill splitter | `fractional_people` | Validation omitted integer check for guest count; calculated instead of error. |

---

## 3. Root Cause & Recommendation Clusters

### Cluster 1: Omission of Whole-Integer Validation on Count Inputs (Count: 9 / 9, 100%)
- **Root Cause Pattern:** The model consistently validates presence (`isNaN`) and sign (`bill >= 0`, `people > 0`, `tip >= 0`), but routinely omits checking whether the denominator / people count is a whole integer. It parses with `parseFloat()` without verifying `Math.floor(n) === n` or `Number.isInteger(n)`.
- **Recommended Prompt Change Pattern:** Explicitly instruct the model to ensure all count inputs (e.g., people/participants) are strictly positive whole integers before performing any calculation.

### Cluster 2: Failure to Suppress `#result` on Invalid Input (Count: 9 / 9, 100%)
- **Root Cause Pattern:** When an invalid or uncomputable input is submitted, the code either proceeds directly to compute and render the per-person amount in `#result`, or renders both the error message and an invalid computed value.
- **Recommended Prompt Change Pattern:** Explicitly instruct that on any invalid input, display the error in `#error` and ensure `#result` is left completely empty or hidden.

---

## 4. Synthesized Candidate Patches

Both candidates are short, general rules validating all numeric inputs before computing. Neither mentions test names, specific values like `2.5`, or element IDs beyond those in the specification (`#bill`, `#people`, `#tip`, `#calc`, `#result`, `#error`).

### Candidate A (Type & Integer Constraint Emphasis)
```
Validate all inputs before computing. The bill and tip must be non-negative numbers, and the number of people must be a positive whole integer. If any input is empty, non-numeric, negative, or not a whole integer, display a clear message in #error and keep #result empty or hidden.
```

### Candidate B (Pre-Calculation Condition Checklist)
```
Before performing any calculation, check every numeric input. Verify that the bill is zero or greater, the tip percentage is zero or greater, and the number of people is a whole number greater than zero. On any invalid input, show an error message in #error and do not display anything in #result.
```
