# Guide: run order, commits, posts

## Run order (real runs)
1. `pytest -q`
2. Fill `PRICES` in `agent/llm.py`; set `.env`.
3. `python -m experiments.smoke --mode baseline --n 5`, then open the neatlogs dashboard and screenshot the failing trace.
4. `python -m experiments.patch_lab`, read `evidence/patches/winner.txt`, edit if needed.
5. `python -m experiments.ab --repeats 1`, then paste trace links into `evidence/metrics.json` → `neatlogs_trace_links`.
6. `python -m cfo.bridge`, paste into cfo.ai, save the export in `evidence/cfo/`, set `business.runway_months` in `assumptions.yaml`.
7. Run the UI, do one live run with Baseline, approve it, then try a run with budget 0.0001 to show a rail firing.
8. Record the demo. Use Replay if the API is slow. Export the Founder Report.

## Suggested commits (you make them; Entire checkpoints attach per commit)
1. `Scaffold project, config, assumptions, requirements`
2. `Add Gemini wrapper with backoff, cost capture and run stats`
3. `Add sandbox, templates, Playwright checks and fixtures`
4. `Add builder loop, trust rails and neatlogs tracing`
5. `Add Flight Recorder autopsy and Patch Lab`
6. `Add A/B experiment, metrics and Cost Radar`
7. `Add verdict rules and cfo.ai bridge`
8. `Add FastAPI server with SSE, replay, approve and kill`
9. `Add pixel office UI, evidence locker, trust panel and simulator`
10. `Add README judge table and guide`

## Build-in-public posts (#neatHack, at least 6 dated)
Kickoff, first traced run, first failure and what the trace showed, before/after counts incl. held-out, cfo.ai plan, demo + repo.
Never post API keys or private links in screenshots.
