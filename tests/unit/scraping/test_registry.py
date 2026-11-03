import pytest

from rosehill.config import Settings
from rosehill.scraping.registry import available_sources, build_lot_source


def test_builds_the_configured_source() -> None:
    source = build_lot_source(Settings(_env_file=None, source="demo"))
    assert source.name == "demo"


def test_unknown_source_lists_the_options() -> None:
    with pytest.raises(ValueError, match="demo"):
        build_lot_source(Settings(_env_file=None, source="nope"))


def test_demo_is_available() -> None:
    assert "demo" in available_sources()
