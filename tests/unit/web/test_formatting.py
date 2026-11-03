from datetime import UTC, datetime, timedelta

import pytest

from rosehill.web.formatting import fuse_percent, time_left_text, urgency

NOW = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("left", "text"),
    [
        (timedelta(seconds=-5), "closing"),
        (timedelta(seconds=0), "closing"),
        (timedelta(seconds=42), "0:42"),
        (timedelta(minutes=7, seconds=5), "7:05"),
        (timedelta(minutes=59, seconds=59), "59:59"),
        (timedelta(hours=1, minutes=5), "1h 05m"),
        (timedelta(hours=2, minutes=0, seconds=30), "2h 00m"),
    ],
)
def test_time_left_text(left: timedelta, text: str) -> None:
    assert time_left_text(left) == text


@pytest.mark.parametrize(
    ("left", "level"),
    [
        (timedelta(minutes=-1), "closing"),
        (timedelta(minutes=3), "now"),
        (timedelta(minutes=5), "now"),
        (timedelta(minutes=12), "soon"),
        (timedelta(minutes=15), "soon"),
        (timedelta(minutes=16), "later"),
    ],
)
def test_urgency(left: timedelta, level: str) -> None:
    assert urgency(left) == level


def test_fuse_percent_is_share_of_window_clamped() -> None:
    assert fuse_percent(timedelta(minutes=15), window_minutes=60) == 25.0
    assert fuse_percent(timedelta(minutes=90), window_minutes=60) == 100.0
    assert fuse_percent(timedelta(minutes=-2), window_minutes=60) == 0.0
