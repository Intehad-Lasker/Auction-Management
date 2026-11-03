from pathlib import Path

import pytest
from pydantic import ValidationError

from rosehill.config import Settings


def test_defaults_point_at_local_sqlite_and_rosehill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROSEHILL_DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///data/rosehill.db"
    assert settings.source_base_url == "https://rosehillonline.ca"
    assert settings.timezone == "America/Toronto"
    assert settings.request_interval_seconds >= 1.0


def test_values_come_from_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROSEHILL_DATABASE_URL", "sqlite:///tmp/test.db")
    monkeypatch.setenv("ROSEHILL_REQUEST_INTERVAL_SECONDS", "3.5")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite:///tmp/test.db"
    assert settings.request_interval_seconds == 3.5


def test_values_come_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ROSEHILL_TIMEZONE=America/Vancouver\n")
    assert Settings(_env_file=env_file).timezone == "America/Vancouver"


def test_request_interval_below_one_second_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, request_interval_seconds=0.2)


def test_unknown_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, timezone="Mars/Olympus")
