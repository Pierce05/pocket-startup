I am planning pricing, costs, revenue and runway for an AI agent product called Pocket Startup. It turns a startup idea into a tested single-file web app plus a viability verdict.
Every figure below carries a tag: MEASURED (from traced runs), COMPUTED (from list price, formulas or conversions), USER-PROVIDED (from founder input) or ASSUMED (business assumptions).

## Measured and computed metrics (improved arm, combined sets)
- runs analysed: 40 [MEASURED]
- success rate: 0.97 [MEASURED]
- first-attempt pass rate: 0.90 [MEASURED]
- average tokens per run: 3524 [MEASURED]
- median latency per run in seconds: 10.22 [MEASURED]
- cost per successful build: $0.006863 [COMPUTED]
- retry tax (share of cost spent after first attempt): 0.18 [COMPUTED]
- gross margin: 0.95 [COMPUTED]
- runway: 12.22 months [COMPUTED]

## Failures by test
- baseline fractional_people failures: 33 [MEASURED]
- baseline split_basic failures: 5 [MEASURED]
- improved split_basic failures: 4 [MEASURED]

## Known limitation on pool-style ideas
- known limitation note: pool-style ideas (e.g. SalonPool Tips) failed split_basic with actual $5.00 [MEASURED] vs expected $30.00 [ASSUMED] (manual founder observation was $20.00 [USER-PROVIDED]), because template notes specify a per-person total bill amount while pool ideas distribute the tip pool only [ASSUMED]

## Founder profile
- target user: Hair salon owners and managers [USER-PROVIDED]
- payer: Salon owners [USER-PROVIDED]
- starting budget: 250000 INR [USER-PROVIDED]
- weekly hours: 30 hours per week [USER-PROVIDED]
- skills: b2b sales, python [USER-PROVIDED]
- goal: Launch profitable tip-splitting micro-SaaS [USER-PROVIDED]
- first customer channel: Local salon visits and cold outreach [USER-PROVIDED]
- demand evidence: interviews [USER-PROVIDED]
- customer price per run: 50.0 INR [USER-PROVIDED]

## Business assumptions
- currency conversion rate (usd to inr): 85.00 [ASSUMED]
- infrastructure cost per run: $0.02 [ASSUMED]
- fixed monthly operating costs: 20000 INR [ASSUMED]
- runs per customer per month: 20 [ASSUMED]
- customers in month one: 10 [ASSUMED]
- customers in month twelve: 200 [ASSUMED]
- kill threshold for success rate: 0.50 [ASSUMED]
- build threshold for success rate: 0.80 [ASSUMED]
- kill threshold for gross margin: 0.20 [ASSUMED]
- build threshold for gross margin: 0.60 [ASSUMED]
- kill threshold for runway: 6.00 months [ASSUMED]
- build threshold for runway: 12.00 months [ASSUMED]
- build threshold for retry tax: 0.35 [ASSUMED]

## Request for CFO plan
Produce: three pricing options with a recommendation, unit economics, gross margin, twelve-month projections in base and growth scenarios, runway, and the assumptions that change the outcome most. Keep the MEASURED, COMPUTED, USER-PROVIDED and ASSUMED tags on every number you report.
