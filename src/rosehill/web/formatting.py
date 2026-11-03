"""Display helpers shared by templates and mirrored by static/countdown.js."""

from __future__ import annotations

from datetime import timedelta

NOW_MINUTES = 5
SOON_MINUTES = 15


def time_left_text(left: timedelta) -> str:
    seconds = int(left.total_seconds())
    if seconds <= 0:
        return "closing"
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    hours, rest = divmod(seconds, 3600)
    return f"{hours}h {rest // 60:02d}m"


def urgency(left: timedelta) -> str:
    """'now' (5 min or less), 'soon' (15 min or less), 'later', or 'closing' if past due."""
    if left <= timedelta(0):
        return "closing"
    if left <= timedelta(minutes=NOW_MINUTES):
        return "now"
    if left <= timedelta(minutes=SOON_MINUTES):
        return "soon"
    return "later"


def fuse_percent(left: timedelta, window_minutes: int) -> float:
    share = left / timedelta(minutes=window_minutes)
    return round(max(0.0, min(1.0, share)) * 100, 1)
