import os
import stat
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_secrets(tmp_path, monkeypatch):
    """Redirect ~/.meetdub/ at the module level so tests can't trash the user's real secrets."""
    monkeypatch.setattr("meetdub.config.CONFIG_DIR", tmp_path)
    monkeypatch.setattr("meetdub.config.CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr("meetdub.secrets.SECRETS_PATH", tmp_path / "secrets.env")
    return tmp_path


def test_round_trip(isolated_secrets):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "sk-test-key")
    assert secrets.read_all() == {"OPENAI_API_KEY": "sk-test-key"}


def test_chmod_600(isolated_secrets):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "sk-test")
    mode = stat.S_IMODE(Path(secrets.SECRETS_PATH).stat().st_mode)
    assert mode == 0o600


def test_overwrites_existing_value(isolated_secrets):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "first")
    secrets.set_value("OPENAI_API_KEY", "second")
    assert secrets.read_all()["OPENAI_API_KEY"] == "second"


def test_clear_specific_keys(isolated_secrets):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "k")
    secrets.set_value("AZURE_OPENAI_API_KEY", "k2")
    secrets.clear_keys(["OPENAI_API_KEY"])
    remaining = secrets.read_all()
    assert "OPENAI_API_KEY" not in remaining
    assert remaining["AZURE_OPENAI_API_KEY"] == "k2"


def test_clear_all_removes_file(isolated_secrets):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "k")
    secrets.clear_keys(None)
    assert not Path(secrets.SECRETS_PATH).exists()


def test_load_into_env_does_not_override_existing(isolated_secrets, monkeypatch):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "from-file")
    monkeypatch.setenv("OPENAI_API_KEY", "from-shell")
    loaded = secrets.load_into_env()
    assert os.environ["OPENAI_API_KEY"] == "from-shell"
    assert "OPENAI_API_KEY" not in loaded


def test_load_into_env_fills_missing(isolated_secrets, monkeypatch):
    from meetdub import secrets

    secrets.set_value("OPENAI_API_KEY", "from-file")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    loaded = secrets.load_into_env()
    assert os.environ["OPENAI_API_KEY"] == "from-file"
    assert loaded["OPENAI_API_KEY"] == "from-file"


def test_mask_short_and_long():
    from meetdub.secrets import mask

    assert mask("") == "(empty)"
    assert mask("short") == "*****"
    assert mask("sk-1234567890abcdef") == "sk-1…cdef (19 chars)"


def test_values_with_special_chars_quoted(isolated_secrets):
    from meetdub import secrets

    secrets.set_value("AZURE_OPENAI_ENDPOINT", "value with spaces")
    raw = Path(secrets.SECRETS_PATH).read_text()
    assert '"value with spaces"' in raw
    assert secrets.read_all()["AZURE_OPENAI_ENDPOINT"] == "value with spaces"
