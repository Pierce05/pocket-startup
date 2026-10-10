Pocket Startup PRD v2: Agents You Would Trust to Run Without You Watching
neatHack 2026 · Python · Gemini · Repo: github.com/Pierce05/pocket-startup
For Claude Code: read this whole file before writing anything. Build in the order in Section 13, one build prompt at a time, then stop and wait. You cannot run git. The human makes all commits.
1. Vision
Type a startup idea. One builder agent builds a tiny working web app inside a locked sandbox. It fails a real acceptance check. Its own neatlogs trace is read by a Flight Recorder that diagnoses the failure and proposes a prompt patch. The patch is tested against held-out ideas. Measured costs then flow into a cfo.ai business plan, and the system returns a rule-based verdict: BUILD, PIVOT or KILL. A pixel-art office shows every step live.
The hackathon tagline is Build agents you would trust to run without you watching. So the product is not only an agent that fixes itself. It is an agent whose behavior is bounded, measured and verifiable, with a one-click Evidence Locker that proves every claim.
Positioning against other teams: several teams show an agent that fixes a failure and verifies it. That is table stakes. Our edge is the whole chain: build, fail, diagnose, fix, validate on unseen ideas, price it, decide whether it is worth building, and prove each link.
2. Principles
1. One builder agent. The office characters are driven by events, not by separate agents.
2. Evidence over claims. Every claim in the demo links to a trace, a file or a number in metrics.json.
3. Honest numbers. Every figure is tagged MEASURED, COMPUTED (from list price) or ASSUMED.
4. Deterministic judgement. Pass or fail and BUILD, PIVOT or KILL come from code, not from an LLM opinion.
5. Failure is a feature. Never delete failed runs. Never fake a failure.
6. Bounded autonomy. Budget cap, attempt cap, timeout, sandbox, human approval gate.
3. Judging map
Criterion (weight)
Features that earn it
Agent works (30%)
F1 loop, F2 checks, F10 Trust Rails, F12 Replay
neatlogs, Entire, cfo.ai (25%)
F3 tracing, F4 autopsy, F5 Patch Lab, F8 cfo.ai bridge, F11 Evidence Locker, F16 Provenance
Demo video (20%)
F9 Pixel Office, F7 Verdict, F12 Replay, F14 Founder Report
Building in public (15%)
Posts at each milestone (see Guide)
Usefulness and originality (10%)
F7 Verdict, F6 Cost Radar, F13 Pricing Simulator
4. Feature list
Priority: P0 must ship, P1 should ship, P2 stretch.
P0: the core (ship these first)
F1. Builder loop. Idea in, spec, code, check, retry up to N attempts (default 4). Output is one index.html. Accept when: a clean run completes from the terminal and writes evidence/runs/<id>/ with index.html, events.json, result.json.
F2. Acceptance checks. Playwright headless Chromium, network blocked, 15 second total timeout, scripted interactions per template, console error capture, localStorage/sessionStorage usage fails the check. Accept when: a hand-written good fixture passes and a hand-written buggy fixture fails on the exact expected test.
F3. neatlogs tracing. Use the installed neatlogs-py skill. Spans for plan, each build attempt, acceptance check, autopsy. Tag spans with run_id, mode, attempt, template. Accept when: a run appears in the neatlogs dashboard with spans, tokens, latency and errors.
F4. Flight Recorder autopsy. One LLM call. Input: trace summary, failed check output, generated HTML (first 6000 characters). Output: JSON with root cause, evidence, one recommended prompt change, confidence. Accept when: it cites facts from the check output and code, not only span metadata.
F5. Patch Lab and A/B with held-out set. Test 2 candidate patches on the tuning set, pick the winner by first-attempt pass rate, then compare baseline vs improved on a tuning set and a held-out set of ideas the autopsy never saw. Report counts. Accept when: metrics.json has both sets, all runs kept.
F6. Cost Radar. From run records compute: cost per success (total cost of all runs divided by successes), retry tax (share of total cost spent on attempts after the first), cost split by stage (plan, build, retry, autopsy), tokens per success. Accept when: the numbers appear in metrics.json and in the UI.
F7. Viability Verdict. A deterministic rules engine, defined in Section 8. Output BUILD, PIVOT or KILL plus the reasons, each tagged with its source. Accept when: the same inputs always give the same verdict and every reason shows its numbers.
F8. cfo.ai bridge. Render evidence/cfo/cfo_input.md from metrics.json and assumptions.yaml, every value labeled MEASURED or ASSUMED. The human pastes it into cfo.ai and saves the export. Accept when: the file renders correctly and a test checks that no unlabeled number appears.
F9. Pixel Office UI. Canvas office with five characters reacting to events (Section 11). Accept when: a full run through the browser plays every beat.
P1: the wow layer
F10. Trust Rails. Hard per-run budget cap in USD, attempt cap, wall-clock timeout, sandbox with network blocked, a human approval gate (button) before the built app is marked Approved, and a kill switch. Each rail that triggers is logged. A Trust Report panel lists the rails and whether they fired. Accept when: a test run with a tiny budget stops cleanly and records which rail fired.
F11. Evidence Locker tab. One page. Each claim row links to its proof: neatlogs trace URL, metrics.json field, run folder, Entire checkpoint screenshot, cfo.ai export. Shows file hashes (SHA-256) of metrics.json and the prompt files, plus the exact command to reproduce the experiment. Accept when: a judge can verify every headline claim in under 5 minutes.
F12. Replay mode. Replay any saved run from its events.json in the office at 1x, 2x or 4x. Clearly labeled REPLAY. This protects the demo from slow APIs. Accept when: replay is visually identical to live and works offline.
F13. Pricing Simulator. Client-side sliders for price, runs per customer and success rate. It recomputes gross margin and break-even using the MEASURED cost per success. It answers: what would have to be true for this to be a business? Accept when: moving a slider updates margin and verdict live.
F14. Founder Report export. One self-contained HTML file with idea, built app screenshot, verdict, key numbers, plan summary and links. Accept when: it opens offline.
P2: stretch (only after P0 and P1 are solid)
F15. Idea Gauntlet. Run 3 ideas sequentially and rank them by verdict, cost per success and retry tax.
F16. Provenance panel. Show the commit list with Entire checkpoint references, using Entire's CLI output [VERIFY] the JSON flags in docs.entire.io/cli/commands.
F17. Juice. Sound effects (mutable), confetti, screen shake on failure.
5. Architecture
Browser: Pixel Office, Verdict, Cost Radar, Evidence Locker, Simulator
   ^ SSE events                      ^ REST
   |                                 |
FastAPI server (server/app.py)
   |
   +-- agent/loop.py            plan, build, check, retry (emits events)
   |     +-- agent/llm.py          Gemini wrapper: tokens, cost, backoff
   |     +-- agent/prompts.py      all prompts
   |     +-- agent/templates.py    3 MVP templates and notes
   |     +-- agent/checks.py       Playwright acceptance tests
   |     +-- agent/sandbox.py      run folder, timeouts
   |     +-- agent/rails.py        budget, attempts, timeout, approval gate
   |     +-- agent/tracing.py      neatlogs setup and span helpers
   |     +-- agent/autopsy.py      Flight Recorder
   +-- experiments/patch_lab.py, ab.py, smoke.py
   +-- evidence/metrics.py       aggregation and Cost Radar
   +-- cfo/bridge.py             cfo_input.md renderer
   +-- verdict.py                rules engine
   +-- report/export.py          Founder Report
Stack: Python 3.11+, FastAPI, uvicorn, sse-starlette, google-genai, neatlogs[google-genai], playwright, pytest, python-dotenv, PyYAML. Frontend is plain HTML, CSS and JS with a canvas. No framework.
6. Repo structure
pocket-startup/
  agent/ server/ ui/ experiments/ cfo/ report/ tests/
  tests/fixtures/ good_tip.html bad_tip.html
  evidence/ runs/ traces/ entire/ cfo/ metrics.json
  docs/ PRD.md GUIDE.md
  assumptions.yaml  verdict.py  README.md  requirements.txt
  .env.example
7. Templates and tests
Each template has: description, required DOM ids, template notes (shown to both baseline and improved prompts), and a Playwright acceptance suite.
T1 Tip Splitter (required). ids: #bill #people #tip #calc #result #error. Notes shown to the builder: invalid input must show a message in #error and leave #result empty. Tests: (1) 100, 4 people, 20 percent gives 30.00 each, (2) people = 0 shows #error, (3) negative tip shows #error, (4) blank bill shows #error, (5) non-numeric bill shows #error.
T2 Habit Tracker (P1). ids: #habit-input #add #list .habit .done-btn #streak. Tests: add two habits, mark one done, streak shows 1, empty add is rejected.
T3 Flashcards (P2). ids: #front #back #add-card #next #card-view #flip.
Fixtures (required): good_tip.html passes all T1 tests. bad_tip.html divides by zero and fails test 2. These prove the check is real before any model is involved.
If the baseline passes everything: do not fake a failure. Harden the suite with edge cases that the template notes legitimately describe, re-measure, and if it still passes, switch the experiment story to cost, tokens and retries and say so honestly.
8. Data and rules
Run record (result.json)
Field
Meaning
run_id, mode, template, idea
identity
success, attempts, first_attempt_passed
outcome
input_tokens, output_tokens
MEASURED from Gemini usage metadata (check actual field names in the SDK)
cost_usd, cost_by_stage
COMPUTED from the PRICES dict
latency_s
MEASURED
rails_fired
list of rails that triggered
error
exception text if the run crashed
neatlogs_trace_url
if available
Every run, including crashes, writes a result.json.
metrics.json per arm and per set (tuning, held-out)
n_runs, success_count, first_attempt_pass_count, avg_attempts, avg_tokens, cost_per_success, retry_tax, median_latency_s, plus temperature, model, pricing_date and a sources map tagging each field MEASURED or COMPUTED.
Verdict rules (verdict.py)
Thresholds live in assumptions.yaml and are labeled ASSUMED.
• Inputs: success rate (MEASURED), cost per success (COMPUTED), retry tax (COMPUTED), price per run, infra cost per run, runway months (from the cfo.ai plan, entered by hand), minimum margin, minimum success rate.
• gross margin = (price - cost per success - infra) / price
• KILL if success rate is below 0.5, or gross margin is below 0.2, or runway is below 6 months.
• BUILD if success rate is at least 0.8, gross margin is at least 0.6, runway is at least 12 months, and retry tax is at most 0.35.
• PIVOT otherwise. Reasons list the failing condition with its numbers, and a suggestion table maps each failing condition to a lever (cheaper model, tighter prompt, higher price, fewer attempts).
9. Prompts (put in agent/prompts.py)
PLANNER_SYSTEM
You are the Founder step of Pocket Startup. You receive a startup idea and the supported MVP templates (tip_splitter, habit_tracker, flashcards).
Pick the single best template and write a short product spec. Do not invent features outside the template.
Return ONLY JSON with keys: template, product_name, one_line_pitch, target_user, adaptation_note.
BUILDER_SYSTEM_V1 (baseline)
You are the Engineer. Build a single-file web app as one index.html with inline CSS and JS. No external libraries, no network calls, no localStorage or sessionStorage.
You will receive a product spec, required element ids and template notes. Every listed id must exist.
Output: at most 3 sentences on your approach, then exactly one fenced html code block with the complete file.
BUILDER_SYSTEM_V2 (improved). Do not write this from imagination. It is generated from the Flight Recorder's recommended change, then reviewed by the human. Starting template:
[V1 text]
Before writing code, list the edge cases a user can trigger (empty input, zero, negative, non-numeric). For each, decide the visible behavior and implement it. Never divide by a user-provided number without checking it is greater than zero.
{autopsy_recommended_change}
BUILDER_USER
Product spec:
{spec_json}
Required element ids: {ids}
Template notes: {template_notes}
Build the app now.
Format with json.dumps(spec, indent=2).
RETRY_USER
Your previous attempt failed automated checks.
Failed test: {test_name}
Expected: {expected}
Actual: {actual}
Browser console errors: {console_errors}
Fix the root cause. Do not rewrite unrelated parts. Return the complete corrected index.html in one html code block, preceded by one sentence naming the root cause.
AUTOPSY_SYSTEM
You are the Flight Recorder. You read an agent run and write a crash report.
Input JSON: spans (name, type, duration_ms, tokens, cost_usd, status, error), failed_check (test, expected, actual, console_errors), generated_index_html (possibly truncated).
Prefer evidence from the check output and the code over span metadata.
Return JSON with keys: failed_span, root_cause (one sentence), evidence (2 to 3 facts quoted from the input), recommended_prompt_change (one concrete instruction), confidence (low, medium, high).
Use only facts present in the input. If the input does not support a conclusion, say so.
CFO_INPUT template (rendered by cfo/bridge.py)
I am planning pricing, costs, revenue and runway for an AI agent product called Pocket Startup. It turns a startup idea into a tested single-file web app plus a viability verdict.
MEASURED from {n_runs} real runs traced in neatlogs: success rate {success_rate}; first-attempt pass rate {first_attempt_rate}; average tokens per run {avg_tokens}; median latency {latency_s}s.
COMPUTED from list price ({pricing_date}, model {model}): cost per successful build ${cost_per_success}; retry tax {retry_tax}.
ASSUMED by me: infra per run ${infra_per_run}; customers month 1 and 12: {c1}, {c12}; runs per customer per month {runs_per_customer}; fixed costs per month ${fixed}; starting cash ${cash}.
Produce: 3 pricing options with a recommendation, unit economics, gross margin, 12-month projections in base and growth scenarios, runway, and the assumptions that change the outcome most. Keep MEASURED, COMPUTED and ASSUMED labels on every number.
10. API
Endpoint
Purpose
POST /api/runs (idea, mode, budget_usd)
start a run
GET /api/runs/{id}/events
SSE event stream
GET /api/runs/{id}
run record
POST /api/runs/{id}/approve
human approval gate
POST /api/runs/{id}/kill
kill switch
POST /api/replay/{id}?speed=2
replay stored events
GET /api/metrics
metrics.json
GET /api/verdict
current verdict with reasons
GET /api/evidence
Evidence Locker rows and hashes
GET /api/report/{id}
Founder Report HTML
SSE events: run_started, plan, attempt_started, code_written, check_started, check_failed, check_passed, rail_fired, retry, autopsy, awaiting_approval, approved, run_finished, metrics_ready, verdict_ready.
11. UI spec
Layout: top bar with idea input, Run, mode toggle (baseline or improved), budget field, Replay. Left 60 percent: office canvas. Right 40 percent: tabs Log, Trace, Cost Radar, Verdict, Plan, Trust, Evidence, Simulator. Bottom ticker: live cost, tokens, attempt n of N, rails status.
Look: dark navy #0f1226 background, neon green #39ff88 for success, alarm red #ff3b5c, amber #ffb020 for warnings, cyan #4de1ff for info, paper #f4ecd8 for cards. Headings in Press Start 2P, body in a monospace such as JetBrains Mono. Crisp pixel scaling (image-rendering: pixelated). One consistent palette and few well-made animations beat many rough ones.
Event
Office reaction
run_started
Founder at whiteboard, idea in a speech bubble
plan
Spec card pinned to the wall
attempt_started, code_written
Engineer types, code scrolls on a monitor
check_started
Tester walks over with a clipboard
check_failed
Red alarm light, error text in a bubble, screen shake
autopsy
Flight Recorder black box lights up, crash report card slides out
rail_fired
Padlock slams, amber banner
retry
Engineer facepalm, then typing
check_passed
Green light, PASS stamp, confetti
awaiting_approval
Founder holds an Approve button
metrics_ready, verdict_ready
CFO walks in with a chart, verdict stamp BUILD, PIVOT or KILL
Start with rectangles and emoji sprites. Swap in pixel art last.
12. Test plan
• Unit: check functions against both fixtures, cost math, verdict rules, cfo bridge labeling, rails (tiny budget stops the run), HTML extraction from model replies.
• Integration: one full run with a mocked LLM, one real smoke run.
• Manual: full run through the UI twice, replay run, fresh-clone test following only the README.
• Never mark a step done if tests are failing.
13. Build order and prompts for Claude Code
Build one prompt at a time. After each, list changed files, give the exact verify commands and a suggested commit message, then wait.
B1 Scaffold. Create the folder structure in Section 6, config module reading .env (GEMINI_API_KEY, GEMINI_MODEL, NEATLOGS_API_KEY), assumptions.yaml with the thresholds in Section 8 and placeholder ASSUMED values, .env.example, and a pytest setup.
B2 LLM wrapper. agent/llm.py using google-genai. Async call and json_call. Retry with exponential backoff on 429 and 503, concurrency cap of 2. Read token counts from the response usage metadata (verify the field names in the SDK), compute cost from a PRICES dict that has a pricing_date field. A RunStats object accumulates tokens and cost by stage. Mocked unit tests.
B3 Sandbox, templates, checks, fixtures. Implement Section 7 for T1 only: templates, sandbox.py, checks.py with the sync Playwright API wrapped in asyncio.to_thread, network blocked, a hard 15 second timeout around the whole check, storage usage detection. Create good_tip.html and bad_tip.html. Tests must prove good passes and bad fails on the zero-people test.
B4 Loop, rails, tracing. loop.py per Section 4 F1, rails.py for F10 (budget, attempts, timeout, kill), event emission, result.json written on every exit path including exceptions, tracing.py using the neatlogs-py skill, spans for plan, build attempts, acceptance check. Add experiments/smoke.py (mode, n).
B5 Autopsy and Patch Lab. autopsy.py (F4) and experiments/patch_lab.py (F5 part 1): generate 2 candidate patches from autopsies, run each on the tuning set, save all results, pick the winner by first-attempt pass rate.
B6 Experiment and Cost Radar. experiments/ab.py runs baseline vs improved on the tuning set and the held-out set (idea lists in experiments/ideas.py, with 5 tuning and 5 held-out ideas), writes metrics.json per Section 8, including cost per success and retry tax. Never drop failed runs. Sequential runs.
B7 Verdict and cfo bridge. verdict.py per Section 8 with tests, and cfo/bridge.py rendering the CFO_INPUT template into evidence/cfo/cfo_input.md with a test that every number carries a label.
B8 Server. FastAPI app with the endpoints in Section 10, SSE stream, replay, approval and kill endpoints.
B9 Office UI. ui/ per Section 11 with the five characters, the event map, the right-hand tabs for Log, Cost Radar, Verdict and Plan, and the bottom ticker. Rectangles and emoji first.
B10 Evidence Locker and Replay. Evidence tab with claim rows, links, SHA-256 hashes and the reproduce command, plus the replay controls.
B11 Trust, Simulator, Report. Trust Report panel, Pricing Simulator tab (client-side), Founder Report export. Then, only if everything else works: T2 template, Idea Gauntlet, sound.
14. Definition of done
[ ] A recorded run that fails, is diagnosed from the neatlogs trace, patched and succeeds
[ ] Tuning and held-out results with counts, all runs kept
[ ] Cost Radar numbers visible in the UI
[ ] cfo.ai plan exported, verdict computed from it
[ ] Trust Rails demonstrated at least once (tiny budget run)
[ ] Replay mode works offline
[ ] Evidence Locker lets a judge verify claims in 5 minutes
[ ] README opens with the judge verification table
[ ] All tests pass on a fresh clone
15. Cut order if time runs short
Sound and juice, then Idea Gauntlet, then T3, then Pricing Simulator, then Founder Report, then T2. Never cut: tracing, the failure and fix, the held-out experiment, the cfo.ai plan and verdict, Entire evidence, Replay mode, public posts.
16. Honesty notes (put these in the README)
• Pass and fail are decided by the Playwright suite, not by an LLM.
• The verdict thresholds are assumptions and are labeled as such. The verdict is a decision aid, not a prediction.
• N is small. Counts are reported next to every percentage with the model, temperature and pricing date.
• Costs are computed at list price from measured tokens.
• Things not verified when this was written: exact neatlogs export capabilities, Entire JSON output flags, whether cfo.ai accepts structured input. Their wrappers are isolated so a change touches one file.