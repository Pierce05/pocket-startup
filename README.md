# Pocket Startup

neatHack 2026 project. Type a startup idea; a builder agent builds a tiny web app,
fails an automated check, is diagnosed from its trace, fixes itself, and a CFO plan
is generated from measured run costs.

Status: scaffold only.

## Setup

    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    playwright install chromium
    cp .env.example .env   # then fill in GEMINI_API_KEY and GEMINI_MODEL

## Known limitation: idea/template mismatch

In the headline A/B benchmark on the held-out idea *"A hairdresser tip splitter for a salon team pool"*, runs generating the product plan `"SalonPool Tips"` failed `split_basic`. The automated test check recorded:
- **Expected:** `#result contains 30.00`
- **Actual:** `#result='5.00'` (along with first-attempt variants `#result='TIP PER PERSON\n$5.00'`, `#result='Per-Person Tip Amount\n$5.00'`, `#result='Each team member receives: $5.00'`, and `#result='Per Person Tip: $5.00'`)

A `20.00` reading of the page was observed manually by the founder and is not in the automated evidence.

The template notes ask for a per-person amount (`(bill + tip) / people = 30.00`). However, the idea's pool framing pulled the model toward showing the total or distributing only the tip pool amount (`(100 * 20%) / 4 = 5.00`). The T1 contract fits bill-splitting ideas better than pool-distribution ideas; the test is not wrong, but reflects a mismatch between the pool framing and the bill-splitting contract.

## Judge verification table

(To be filled in at the end.)