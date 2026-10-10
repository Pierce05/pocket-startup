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

## Judge verification table

(To be filled in at the end.)