"""Run folders. Generated code is HTML/JS only and is never executed in Python."""
import datetime
import json
import secrets
from pathlib import Path

import config


def new_run_id() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def run_dir(run_id: str, runs_dir=None) -> Path:
    d = Path(runs_dir or config.RUNS) / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write(run_id: str, name: str, content: str, runs_dir=None) -> Path:
    p = run_dir(run_id, runs_dir) / name
    p.write_text(content, encoding="utf-8")
    return p


def write_json(run_id: str, name: str, obj, runs_dir=None) -> Path:
    return write(run_id, name, json.dumps(obj, indent=2, default=str), runs_dir)
