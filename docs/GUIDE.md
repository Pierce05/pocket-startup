Pocket Startup: End-to-End Guide
Purvanshi · Sat Oct 10, 3:35 PM IST → Mon Oct 12, 11:55 PM IST · Repo: github.com/Pierce05/pocket-startup · Companion doc: PRD v2
This is your day-by-day, step-by-step operating manual. The PRD says what to build. This guide says what you do, when, and how to know it worked.
1. How this works
Who
Job
Claude Code
Writes files into the repo folder, runs tests, proposes commit messages. It cannot run git.
You
Run every command yourself, review every diff, make every commit, push, post, record the demo.
Me (this chat)
Plan, review errors and screenshots you paste, interpret traces, write posts and README text.
Eight golden rules
1. Entire is enabled before Claude Code writes any code, and Claude Code is always launched from inside the pocket-startup folder. That is what makes your checkpoints real.
2. Never accept code you have not run. After every step: pytest, then a smoke run.
3. Commit small and often, after each working step, with a clear message. Then git push.
4. No secrets in git. .env is ignored. Check git status before every git add ..
5. Keep failed runs. Never delete a failing run folder or trace. Failures are your evidence.
6. Label every number MEASURED (from runs or traces) or ASSUMED (your input).
7. Post publicly at every milestone with #neatHack. That is 15% of the score.
8. Screenshot evidence the moment it exists. Do not plan to recreate it later.
Practical warnings
• Your laptop showed 13% battery in the screenshot. Plug in now.
• Sleep. Plan 6 to 7 hours both nights. A tired Monday ruins the demo.
• Your AWS $25 is a shared hard cap that nothing meters for you. You do not need AWS at all. Skip it.
2. Where you are right now
[x] Repo pocket-startup created on GitHub (public, MIT, .gitignore, README, one initial commit)
[x] cfo.ai trial created and subscription cancelled
[x] AWS access (not needed)
[x] Gemini API key
[x] VS Code open on the folder
[ ] Entire installed and enabled
[ ] neatlogs account, API key and skill
[ ] Python environment
[ ] PRD saved into the repo
[ ] First #neatHack post
Your team name from the AWS email is hollanov. Confirm it on the web check-in page, because you will quote it in the final submission tweet.
3. Phase 0: Setup (now until about 5:00 PM)
Open the VS Code terminal with Ctrl + backtick. All commands are PowerShell.
0.1 Confirm the folder is the cloned repo
git status
git remote -v
Done when remote -v shows github.com/Pierce05/pocket-startup. If it says not a git repository, run git clone https://github.com/Pierce05/pocket-startup.git, then File → Open Folder → pick that folder.
0.2 Check your tools
git --version
python --version
node --version
Need Python 3.11 or newer and Node.js. If Node is missing, install the LTS from nodejs.org. If Python is older, install 3.11+ from python.org and tick Add to PATH.
0.3 Install Entire
Open docs.entire.io/cli/installation and follow the Windows instructions there. The Scoop package was renamed recently, so copy the command from the docs and not from memory. Then:
entire version
Done when it prints a version.
0.4 Log in and claim hackathon access
entire login
A browser opens for device auth. Then open hack.entire.io/neathacks-2026 and claim the hackathon access and credits.
0.5 Enable Entire in the repo
entire enable
It creates settings, installs git hooks and asks which agent hooks to install. Choose Claude Code. Done when it reports success with no errors.
0.6 neatlogs: key and skill
1. Go to app.neatlogs.com, sign in, create an API key.
2. Install the official skill so Claude Code uses the correct tracing API:
npx skills add neatlogs/skills --skill "neatlogs-py"
3. Open the neatlogs Docs link and note the exact environment variable name for the key.
0.7 Python environment and packages
python -m venv .venv
.venv/Scripts/Activate.ps1
pip install fastapi uvicorn sse-starlette google-genai playwright pytest python-dotenv "neatlogs[google-genai]"
pip freeze > requirements.txt
playwright install chromium
If PowerShell blocks activation, run Set-ExecutionPolicy -Scope CurrentUser RemoteSigned once and retry. Your prompt should now start with (.venv).
0.8 Secrets files
Create .env:
GEMINI_API_KEY=paste-your-key
GEMINI_MODEL=model-name-from-google-ai-studio
NEATLOGS_API_KEY=paste-your-key
Create .env.example with the same names and empty values. Open .gitignore and confirm it lists .env, .venv/ and __pycache__/.
0.9 Put the PRD into the repo
Create a docs folder and save PRD v2 as docs/PRD.md (copy the text of the PRD doc, or export it as Markdown). Claude Code reads this file, and it becomes part of the captured context.
0.10 First commit
git pull
git status
Check that .env and .venv do not appear. Then:
git add .
git commit -m "Add setup, requirements and PRD v2"
git push
On GitHub confirm the commit appears and no .env is visible. Look for a branch named entire/checkpoints/v1. Screenshot the repo page.
0.11 Post #1
Started neatHack: Pocket Startup. An agent builds a tiny app, fails, gets diagnosed from its own neatlogs trace, fixes itself, then plans its business with cfo.ai. Repo: github.com/Pierce05/pocket-startup #neatHack
Attach the repo screenshot.
Phase 0 gate: entire version works, .venv active, first push done, post #1 live. If Entire fails, send me the exact error.
4. Phase 1: Core loop (Sat about 5:00 PM to 10:30 PM)
4.1 Start Claude Code
claude
Run it from the repo root. Paste this kickoff prompt:
Read docs/PRD.md fully before doing anything. Workflow rules for this whole project: (1) You cannot run git; never try. I make all commits. (2) Write files directly to disk in this folder. After each step, list files created or changed and give me a suggested commit message. (3) Work in small steps: one build prompt (B1 to B11 in the PRD) at a time, then STOP and give me exact commands to verify, and wait for my confirmation. (4) Use the installed neatlogs-py skill for tracing; do not guess API names. (5) The LLM is Gemini via the google-genai SDK; model name comes from GEMINI_MODEL in .env. (6) Never print or hard-code secrets. Start with B1 only.
4.2 Build steps and how you verify each
Step
Claude Code builds
You verify
Commit message
B1
Config, folders, constants
pytest runs (even if empty)
Scaffold project structure
B2
llm.py with Gemini, retry, token and cost capture
pytest, then one tiny real call that prints tokens
Add Gemini wrapper
B3
Sandbox, templates, Playwright checks, fixtures
Good fixture passes, bad fixture fails on the right test
Add acceptance checks and fixtures
B4
Loop, events, result.json, trust rails, neatlogs spans
One full run from the terminal
Add agent loop with tracing
Critical test before moving on (B3): there must be a hand-written correct index.html and a hand-written buggy one in tests/fixtures/. The correct one must pass the check and the buggy one must fail on the zero-people test. This proves the check is real before any model is involved.
After B4, open app.neatlogs.com and look at the run. You should see spans, tokens, latency and any error. Screenshot it. If you see nothing, send me the terminal output.
4.3 Gate G1: does the baseline actually fail?
Run the baseline 5 times:
python -m experiments.smoke --mode baseline -n 5
Write down how many passed on the first attempt.
Result
What to do
1 to 4 of 5 passed first try
Ideal. You have genuine failures. Continue.
5 of 5 passed
Make the acceptance suite stricter in ways the template notes legitimately specify (negative tip, blank field, non-numeric input, exact error text listed in the template notes that BOTH arms see). Re-run.
0 of 5 passed
Check that the check is not broken (run the good fixture). If the check is fine, the model is struggling. Still good for the story, but note V2 must reach a real improvement.
Still 5 of 5 after hardening
Do not fake it. Switch the experiment to cost and retries, or use a harder template. Report honestly.
4.4 Evening wrap-up
• Make sure every step is committed and pushed.
• Run entire checkpoint to list checkpoints. Screenshot it.
• Post #2 with the neatlogs failure screenshot and a one-line explanation.
• Stop by 10:30 PM and sleep.
5. Phase 2: Evidence (Sun 9:00 AM to 2:00 PM)
1. Autopsy (9:00). Run the Flight Recorder on a failed baseline run. It gets the trace summary, the failed check output and the generated code. Read its output yourself. Do you agree with the root cause? Look at the neatlogs trace to confirm.
2. Patch (10:00). Take its recommended prompt change and turn it into the V2 builder prompt. Commit the autopsy output and the V2 prompt together so the link between them is visible in git history.
3. Patch Lab (10:30). Run 2 candidate patches on the tuning set, 5 runs each. Pick the better one by first-attempt pass rate. Save all results, including the loser.
4. Experiment (11:00). python -m experiments.ab runs baseline vs improved on the tuning set AND on held-out ideas the autopsy never saw. This is the proof against overfitting.
5. Evidence (1:00). Screenshot the neatlogs failed trace, the fixed trace and the compare view. Commit evidence/metrics.json.
6. Post #3 with the failure and the diagnosis. Post #4 with the before and after counts.
Report counts, not only percentages (for example 3/10 vs 9/10), and write the model name, temperature and pricing date next to the numbers.
6. Phase 3: Business and verdict (Sun 2:00 PM to 5:00 PM)
1. Run the bridge: python -m cfo.bridge. It writes evidence/cfo/cfo_input.md with every value labeled MEASURED or ASSUMED.
2. Open app.cfo.ai and paste the contents into the chat. Ask for: 3 pricing options, unit economics, 12-month base and growth scenarios, runway, and the assumptions that matter most.
3. Export or screenshot the result into evidence/cfo/. Check Settings → Usage to confirm your credits arrived.
4. Enter the recommended price and runway figures into assumptions.yaml, then run python -m verdict. It produces BUILD, PIVOT or KILL by fixed rules (defined in the PRD), with reasons.
5. Commit and push. Post #5 with the plan screenshot and the verdict.
7. Phase 4: Office UI and the wow layer (Sun 5:00 PM to 11:00 PM)
Build in this order. Stop and keep what works if time runs out.
1. Server and live event stream (B8)
2. Office canvas with five characters reacting to events (B9)
3. Replay mode, so the demo cannot fail on stage (B10)
4. Evidence Locker tab (B10)
5. Trust Rails panel, Pricing Simulator, Founder Report export (B11)
Test the full run through the UI at least twice before bed. Commit after each piece.
7b. Rhythm for each Claude Code step
1. Paste the next build prompt.
2. Wait for it to finish and list changed files.
3. Run the verify commands it gives you plus pytest.
4. Read the diff in VS Code (Source Control tab) for anything surprising.
5. If it works: commit, push. If not: paste the full error back into Claude Code, or to me.
8. Phase 5: Package (Mon Oct 12)
Time (IST)
Task
9:00 to 11:30
Polish: pixel art swap, copy, empty states, error handling. Only if the core is done
11:30 to 12:30
Code freeze. No new features after this
12:30 to 2:00
Fresh-clone test: clone into a new folder, follow only the README, make sure it runs
2:00 to 4:30
Record the demo (3 to 5 takes), pick the best
4:30 to 6:00
Upload the video, finish README, collect all links, write the tweet
6:00 to 6:45
Rest, eat, final check of every link
7:00 sharp
Post the quote tweet
9. Submission-day procedure (7:00 PM IST)
Submit by quoting the official neatlogs post on X with your team, project name, public repo and demo. neatlogs and cfo.ai engage with the first 50 quote tweets, so be early.
Draft:
Team: hollanov (Purvanshi Khandelwal) Project: Pocket Startup. An agent that builds a tiny app, diagnoses its own failures from neatlogs traces, fixes itself, and decides whether the business is worth building with cfo.ai. Repo: github.com/Pierce05/pocket-startup Demo: <video link> #neatHack
Before posting, check: repo is public, video link works while logged out, no secrets anywhere, README opens with a verification table. Check the official rules for the demo length limit and exact quote format.
10. Posting calendar
#
When
Content
1
Sat evening
Idea and repo (draft in Phase 0)
2
Sat night
First traced run in neatlogs
3
Sun morning
First genuine failure and the diagnosis
4
Sun afternoon
Before and after numbers
5
Sun evening
cfo.ai plan and the BUILD, PIVOT or KILL verdict
6
Mon
Demo video and repo
Each post gets a screenshot and one plain sentence about what you learned. Never post keys, the AWS link or card details.
11. Evidence locker (screenshot as you go)
Evidence
Folder
neatlogs failed trace with error
evidence/traces/
neatlogs fixed trace
evidence/traces/
neatlogs compare view
evidence/traces/
Entire checkpoint list and one expanded checkpoint
evidence/entire/
entire-graph or repo map, if it works
evidence/entire/
metrics.json (tuning and held-out)
evidence/
cfo.ai input and exported plan
evidence/cfo/
cfo.ai usage page with credits
evidence/cfo/
Verdict output
evidence/
12. Decision gates and fallbacks
If
Then
neatlogs shows no data
Check the key variable name in the docs, check the skill was followed, send me the terminal output
neatlogs cannot export data
Use your own events.json as the data source and screenshot the dashboard
Gemini rate limits (429)
Add sleeps between runs, lower N temporarily, use the cheaper model for experiments
Entire shows no checkpoint
You enabled it after Claude Code started, or launched it outside the repo. Re-enable, restart Claude Code from the repo, and commit again
cfo.ai will not take structured input
Paste the markdown into chat and screenshot the answer
Time is short on Monday
Cut in this order: pixel-art polish, Idea Gauntlet, Pricing Simulator, T3, animations. Never cut tracing, the experiment, cfo.ai, Entire evidence or posts
13. Troubleshooting quick list
• Activate.ps1 blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
• playwright install fails: retry on a stable connection, then playwright install chromium again
• ModuleNotFoundError: the venv is not active. Run .venv/Scripts/Activate.ps1
• git push rejected: run git pull first, then push again
• A secret was committed: do not just delete it. Rotate the key immediately, then tell me and we will clean the history
• Check hangs: the generated page has an infinite loop. Make sure the 15 second timeout wraps the whole check
14. Demo recording guide
• Tools: OBS Studio, Windows Game Bar (Win + G) or Clipchamp. Record at 1080p.
• Browser zoom 110%, notifications off, one clean window, tabs prepared in order: office UI, neatlogs trace, neatlogs compare, Entire checkpoint, cfo.ai plan, GitHub repo.
• Use Replay mode for the main run so a slow API call cannot ruin a take. Say clearly that it is a replay of a real recorded run and show the live trace link.
• Script (confirm the length limit in the rules): 0:00 idea and office, 0:25 first failure, 1:05 neatlogs diagnosis, 1:50 before and after numbers, 2:15 verdict and cfo.ai plan, 2:45 Entire checkpoints and repo.
• Lead with the failure and the fix. Judges can verify it, and it is your strongest 30 seconds.
• Rehearse twice, then record. Speak slowly.
15. Final checklist
[ ] Public repo, history starts after Oct 10, 12:30 PM IST
[ ] Entire checkpoints visible, entire/checkpoints/v1 pushed
[ ] neatlogs: failed trace, fixed trace, compare view
[ ] metrics.json with tuning and held-out counts
[ ] cfo.ai plan exported, MEASURED and ASSUMED labels
[ ] Verdict screen working
[ ] Replay mode working
[ ] README with the judge verification table
[ ] 6 posts live
[ ] Demo uploaded and tested logged out
[ ] No secrets in repo or screenshots
[ ] Quote tweet posted at 7:00 PM IST