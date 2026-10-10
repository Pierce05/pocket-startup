import pytest

import config


@pytest.fixture(autouse=True)
def tmp_evidence(tmp_path, monkeypatch):
    ev = tmp_path / "evidence"
    (ev / "runs").mkdir(parents=True)
    (ev / "patches").mkdir()
    (ev / "cfo").mkdir()
    monkeypatch.setattr(config, "EVIDENCE", ev)
    monkeypatch.setattr(config, "RUNS", ev / "runs")
    monkeypatch.setattr(config, "METRICS_PATH", ev / "metrics.json")
    monkeypatch.setattr(config, "PATCH_DIR", ev / "patches")
    monkeypatch.setattr(config, "CFO_DIR", ev / "cfo")
    return ev


def _browser_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


BROWSER = _browser_available()
needs_browser = pytest.mark.skipif(not BROWSER, reason="Chromium not installed (run: playwright install chromium)")
