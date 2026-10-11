Founder file: founder_a.yaml, cohort: held_out

I am planning pricing, costs, revenue and runway for an AI agent product called Pocket Startup. It turns a startup idea into a tested single-file web app plus a viability verdict.
The unit of sale is one run: one tested single-file app build delivered to a customer; the customer is Office teams who run shared coffee and lunch orders; price is per run in INR.
Every figure below carries a tag: MEASURED (from traced runs), COMPUTED (from list price, formulas or conversions), USER-PROVIDED (from founder input) or ASSUMED (business assumptions).

## Measured and computed metrics (improved arm, held_out cohort)
- runs analysed: 20 [MEASURED]
- success rate: 0.95 [MEASURED] (baseline: 0.75 [MEASURED])
- first-attempt pass rate: 0.80 [MEASURED] (baseline: 0.05 [MEASURED])
- average tokens per run: 4495 [MEASURED]
- median latency per run in seconds: 10.68 [MEASURED]
- cost per successful build: $0.008397 [COMPUTED] (baseline: $0.023148 [COMPUTED])
- retry tax (share of cost spent after first attempt): 0.31 [COMPUTED] (baseline: 0.63 [COMPUTED])

## Failures by test
- baseline fractional_people failures: 14 [MEASURED]
- baseline split_basic failures: 5 [MEASURED]
- improved split_basic failures: 4 [MEASURED]

## Known limitation on pool-style ideas
- known limitation note: pool-style ideas (e.g. SalonPool Tips) failed split_basic with actual $5.00 [MEASURED] vs expected $30.00 [CONFIG] (manual founder observation was $20.00 [USER-PROVIDED]), because template notes specify a per-person total bill amount while pool ideas distribute the tip pool only [OBSERVATION]

## Founder profile
- target user: Office teams who run shared coffee and lunch orders [USER-PROVIDED]
- payer: Office managers [USER-PROVIDED]
- starting budget: 350000 INR [USER-PROVIDED]
- weekly hours: 40 hours per week [USER-PROVIDED]
- skills: b2b sales, python [USER-PROVIDED]
- goal: Per-person bill and tip splitting for office group orders [USER-PROVIDED]
- first customer channel: Direct outreach to office managers [USER-PROVIDED]
- demand evidence: interviews [USER-PROVIDED]
- customer price per run: 50.0 INR [USER-PROVIDED]

## Business assumptions
- currency conversion rate (usd to inr): 85.00 [ASSUMED]
- infrastructure cost per run: $0.02 [ASSUMED]
- fixed monthly operating costs: 20000 INR [ASSUMED]
- runs per customer per month: 20 [ASSUMED]
- customers in month one: 10 [ASSUMED]
- customers in month twelve: 200 [ASSUMED]

## Pocket Startup's own estimates, for comparison only
- gross margin: 0.95 [COMPUTED]
- runway: 17.09 months [COMPUTED]

## Request for CFO plan
Produce: three pricing options with a recommendation, unit economics, gross margin, twelve-month projections in base and growth scenarios, runway, and the assumptions that change the outcome most. Keep the MEASURED, COMPUTED, USER-PROVIDED and ASSUMED tags on every number you report. If you introduce any number that is not in this file, label it [CFO.AI-ASSUMED] and list those numbers separately.
