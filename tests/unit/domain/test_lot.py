from datetime import UTC, datetime, timedelta

import pytest

from rosehill.domain.lot import ScrapedLot
from rosehill.domain.money import Money

CLOSES = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)


def make(**overrides: object) -> ScrapedLot:
    fields: dict[str, object] = {
        "source_id": "A1-001",
        "title": "Dyson V8 vacuum",
        "current_bid": Money(4500),
        "bid_count": 3,
        "closes_at": CLOSES,
        "url": "https://rosehillonline.ca/lot/A1-001",
    }
    fields.update(overrides)
    return ScrapedLot(**fields)  # type: ignore[arg-type]


def test_optional_fields_default_to_empty() -> None:
    lot = make()
    assert lot.photos == ()
    assert lot.pickup_location is None
    assert lot.category is None
    assert lot.is_closed is False


def test_closing_time_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone"):
        make(closes_at=datetime(2026, 11, 3, 20, 0))


def test_closing_time_is_normalised_to_utc() -> None:
    from zoneinfo import ZoneInfo

    toronto = datetime(2026, 11, 3, 15, 0, tzinfo=ZoneInfo("America/Toronto"))
    assert make(closes_at=toronto).closes_at == CLOSES
    assert make(closes_at=toronto).closes_at.tzinfo is UTC


def test_negative_bid_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="bid_count"):
        make(bid_count=-1)


def test_negative_bid_is_rejected() -> None:
    with pytest.raises(ValueError, match="current_bid"):
        make(current_bid=Money(-1))


def test_blank_title_or_source_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        make(title="  ")
    with pytest.raises(ValueError):
        make(source_id="")


def test_time_left() -> None:
    now = CLOSES - timedelta(minutes=42)
    assert make().time_left(now) == timedelta(minutes=42)
