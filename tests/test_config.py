import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _openai_api_key_for_config_imports(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-unit-tests")


def test_settings_openai_api_key_has_no_default():
    from app.config import Settings

    fields = Settings.model_fields
    assert "openai_api_key" in fields
    assert fields["openai_api_key"].is_required()


def test_settings_model_name_defaults_to_gpt_4o_mini():
    from app.config import Settings

    settings = Settings()
    assert settings.model_name == "gpt-4o-mini"


def test_config_module_import_fails_without_openai_api_key():
    """Module-level settings = Settings() must fail when OPENAI_API_KEY is unset."""
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "openai_api_key" in (result.stderr or result.stdout)
    assert "ValidationError" in (result.stderr or result.stdout)
