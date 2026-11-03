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


def test_scrape_without_dry_run_is_not_available_yet(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["scrape"])
    assert exc.value.code == 2
    assert "--dry-run" in capsys.readouterr().err
