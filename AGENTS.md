# Pocket Startup: standing instructions
Project: neatHack 2026 agent. Python, Gemini API, neatlogs, Entire, cfo.ai.
Spec: docs/PRD.md. Operating manual: docs/GUIDE.md. Read the PRD before any task.
Reference implementation (generated in a chat, untested against real Chromium, Gemini or neatlogs): reference/pocket-startup. Review it file by file; never bulk-copy.

RULES
1. Git: you may run read-only git commands (status, diff, log). ONLY when I say 'commit', stage specific files by name (never 'git add -A', 'git add .' or -f), then run: git grep --cached -n -E "AIza|sk-[A-Za-z0-9]{20,}" . If that prints anything, or git status shows .env, .venv or reference/ staged, STOP and tell me. Otherwise commit with the message you suggested. NEVER run git push, force, reset, clean, checkout, rebase, stash, or delete branches, and never touch .git or hooks. I push myself. After each stage list files changed, verify commands and a commit message, then STOP and wait for 'approved'.
2. Secrets only from .env / environment. Never print, log or hard-code them. Never read or show .env contents.
3. Do not invent APIs. cfo.ai has no verified API: the bridge only renders evidence/cfo/cfo_input.md for the human to paste by hand. Verify neatlogs calls against the installed skill in .agents/skills/neatlogs-py. Do not claim Entire captured anything until `entire checkpoint` shows it. Mark unknowns [VERIFY].
4. Pass or fail comes from Playwright code, never from an LLM. Mock runs are labelled MOCK and excluded from metrics. Never delete failed runs. Tag every number MEASURED, COMPUTED or ASSUMED.
5. Never weaken or delete a failing test to make it pass.
6. Do not use subagents.

STAGES (one at a time, in order)
0 Inspect only, report, wait.
1 Core agent, checks, rails, tracing, one real smoke run.
2 Autopsy, patch lab, A/B with held-out set, cost radar.
3 Verdict and cfo bridge.
4 Server, Pixel Office, Replay, Evidence Locker.
5 Trust UI, Pricing Simulator, Founder Report.
6 Hardening and fresh-clone test.
