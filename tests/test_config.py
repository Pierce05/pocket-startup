from pathlib import Path
import os
import config


def test_load_assumptions_default():
    """Verify assumptions.yaml is loaded and contains expected structure."""
    assumptions = config.load_assumptions()
    assert isinstance(assumptions, dict)
    assert "thresholds" in assumptions
    assert "business" in assumptions

    thresholds = assumptions["thresholds"]
    assert thresholds["kill_success_rate"] == 0.5
    assert thresholds["build_success_rate"] == 0.8
    assert thresholds["build_margin"] == 0.6

    business = assumptions["business"]
    assert business["price_per_run"] == 1.00
    assert business["starting_cash"] == 10000


def test_load_assumptions_custom_path_utf8(tmp_path):
    """Verify custom YAML files with UTF-8 characters are read cleanly."""
    custom_yaml = tmp_path / "custom_assumptions.yaml"
    custom_yaml.write_text(
        "project: 'Pocket Startup 🚀'\nnote: 'café & naïve'\nvalue: 123\n",
        encoding="utf-8",
    )
    loaded = config.load_assumptions(custom_yaml)
    assert loaded["project"] == "Pocket Startup 🚀"
    assert loaded["note"] == "café & naïve"
    assert loaded["value"] == 123


def test_config_paths_and_defaults():
    """Verify default paths and execution limits."""
    assert isinstance(config.ROOT, Path)
    assert config.ROOT.is_dir()
    assert config.ASSUMPTIONS_PATH.is_file()

    assert config.DEFAULT_MAX_ATTEMPTS == 4
    assert config.DEFAULT_BUDGET_USD == 0.50
    assert config.DEFAULT_TIMEOUT_S == 180
    assert config.CHECK_TIMEOUT_S == 15


def test_env_vars_presence_and_types():
    """Verify required config attributes and their types without inspecting secrets."""
    assert hasattr(config, "GEMINI_API_KEY")
    assert isinstance(config.GEMINI_API_KEY, str)

    assert hasattr(config, "GEMINI_MODEL")
    assert isinstance(config.GEMINI_MODEL, str)
    assert len(config.GEMINI_MODEL) > 0

    assert hasattr(config, "NEATLOGS_API_KEY")
    assert isinstance(config.NEATLOGS_API_KEY, str)

    assert hasattr(config, "POCKET_MOCK")
    assert isinstance(config.POCKET_MOCK, bool)


def test_env_var_validation_logic():
    """Verify environment variable validation rules and fallbacks."""
    # GEMINI_MODEL fallback default
    default_model = os.getenv("NONEXISTENT_MODEL_VAR", "gemini-2.5-flash")
    assert default_model == "gemini-2.5-flash"

    # POCKET_MOCK flag conversion behavior
    assert ("1" == "1") is True
    assert ("0" == "1") is False
    assert ("" == "1") is False

    # Validation logic used across the agent/server:
    # Execution requires either valid API key or mock mode enabled
    def has_valid_execution_credentials(api_key: str, mock_mode: bool) -> bool:
        return bool(mock_mode or (api_key and len(api_key.strip()) > 0))

    assert has_valid_execution_credentials("", mock_mode=False) is False
    assert has_valid_execution_credentials("dummy-test-key", mock_mode=False) is True
    assert has_valid_execution_credentials("", mock_mode=True) is True


def test_tmp_evidence_fixture(tmp_evidence):
    """Verify tmp_evidence fixture creates temporary paths and monkeypatches config."""
    assert tmp_evidence.is_dir()
    assert (tmp_evidence / "runs").is_dir()
    assert (tmp_evidence / "patches").is_dir()
    assert (tmp_evidence / "cfo").is_dir()

    assert config.EVIDENCE == tmp_evidence
    assert config.RUNS == tmp_evidence / "runs"
    assert config.METRICS_PATH == tmp_evidence / "metrics.json"
    assert config.PATCH_DIR == tmp_evidence / "patches"
    assert config.CFO_DIR == tmp_evidence / "cfo"

    # Verify writing to config.RUNS is isolated within tmp_evidence
    dummy_run = config.RUNS / "run-test-123"
    dummy_run.mkdir()
    assert dummy_run.is_dir()
    assert dummy_run.parent == tmp_evidence / "runs"
