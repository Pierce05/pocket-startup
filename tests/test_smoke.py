import pytest

import config
from experiments import smoke
from tests.conftest import needs_browser


def test_smoke_arg_parsing_defaults():
    args = smoke.parse_args([])
    assert args.mode == "baseline"
    assert args.n == 1
    assert args.mock is False
    assert args.idea is None


def test_smoke_arg_parsing_custom():
    args = smoke.parse_args(["--mode", "improved", "--n", "3", "--mock", "--idea", "Split dinner tab"])
    assert args.mode == "improved"
    assert args.n == 3
    assert args.mock is True
    assert args.idea == "Split dinner tab"


async def test_smoke_missing_credentials_raises(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        await smoke.run_smoke(mock=False)


@needs_browser
async def test_smoke_mock_mode_execution(tmp_evidence):
    results = await smoke.run_smoke(mode="baseline", n=1, mock=True, emit=lambda *a: None)
    assert len(results) == 1
    rec = results[0]
    assert rec["mock"] is True
    assert rec["success"] is True
    assert rec["attempts"] == 2
    assert not rec["first_attempt_passed"]

    # Verify run artifacts were written
    run_path = config.RUNS / rec["run_id"]
    assert (run_path / "result.json").exists()
    assert (run_path / "events.json").exists()
    assert (run_path / "index.html").exists()


def test_smoke_cli_main_missing_key(monkeypatch, capsys):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    with pytest.raises(SystemExit) as exc_info:
        smoke.main([])
    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "GEMINI_API_KEY is not set" in err


@needs_browser
def test_smoke_cli_main_mock(capsys):
    results = smoke.main(["--mock", "--n", "1"])
    assert len(results) == 1
    out = capsys.readouterr().out
    assert "[MOCK - excluded from metrics]" in out
    assert "[MEASURED]" in out
    assert "[COMPUTED:" in out
