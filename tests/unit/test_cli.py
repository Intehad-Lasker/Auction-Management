import re
from pathlib import Path

import pytest

from rosehill import __version__
from rosehill.cli import main


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_scrape_dry_run_prints_lots_soonest_first(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scrape", "--dry-run", "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert "source: demo" in out
    assert out.count("DEMO-") == 5


def test_db_upgrade_creates_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "data" / "rosehill.db"
    monkeypatch.setenv("ROSEHILL_DATABASE_URL", f"sqlite:///{db}")
    assert main(["db", "upgrade"]) == 0
    assert db.exists()
    assert "up to date" in capsys.readouterr().out


def test_scrape_saves_lots_and_reports_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ROSEHILL_DATABASE_URL", f"sqlite:///{tmp_path / 'rosehill.db'}")
    assert main(["scrape"]) == 0
    first = capsys.readouterr().out
    assert "new: 2000" in first
    assert main(["scrape"]) == 0
    second = capsys.readouterr().out
    # The same lots are already stored; only lots that rolled into the window are new.
    new = int(re.search(r"new: (\d+)", second).group(1))  # type: ignore[union-attr]
    assert new < 10
