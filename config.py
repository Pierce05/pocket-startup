"""Central config. Modules read paths via `config.X` at call time so tests can monkeypatch them."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", encoding="utf-8")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
NEATLOGS_API_KEY = os.getenv("NEATLOGS_API_KEY", "")
POCKET_MOCK = os.getenv("POCKET_MOCK", "0") == "1"

EVIDENCE = ROOT / "evidence"
RUNS = EVIDENCE / "runs"
METRICS_PATH = EVIDENCE / "metrics.json"
PATCH_DIR = EVIDENCE / "patches"
CFO_DIR = EVIDENCE / "cfo"
ASSUMPTIONS_PATH = ROOT / "assumptions.yaml"

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BUDGET_USD = 0.50
DEFAULT_TIMEOUT_S = 180
CHECK_TIMEOUT_S = 15


def load_assumptions(path=None):
    p = Path(path) if path else ASSUMPTIONS_PATH
    return yaml.safe_load(p.read_text(encoding="utf-8"))
