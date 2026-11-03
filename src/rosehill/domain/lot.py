"""Lot data as reported by a lot source, independent of how it was scraped or stored."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from rosehill.domain.money import Money


class LotStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class ScrapedLot:
    """One lot as seen by a `LotSource` at a moment in time."""

    source_id: str
    title: str
    current_bid: Money
    bid_count: int
    closes_at: datetime
    url: str
    photos: tuple[str, ...] = field(default=())
    pickup_location: str | None = None
    category: str | None = None
    auction_id: str | None = None
    is_closed: bool = False

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be blank")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if self.bid_count < 0:
            raise ValueError("bid_count must not be negative")
        if self.current_bid.cents < 0:
            raise ValueError("current_bid must not be negative")
        if self.closes_at.tzinfo is None:
            raise ValueError("closes_at must be timezone-aware")
        object.__setattr__(self, "closes_at", self.closes_at.astimezone(UTC))

    def time_left(self, now: datetime) -> timedelta:
        return self.closes_at - now


@dataclass(frozen=True, slots=True)
class StoredLot:
    """A lot as the app knows it: the latest scraped values plus tracking fields."""

    id: int
    source: str
    source_id: str
    title: str
    current_bid: Money
    bid_count: int
    closes_at: datetime
    status: LotStatus
    url: str
    first_seen_at: datetime
    last_scraped_at: datetime
    photos: tuple[str, ...] = field(default=())
    pickup_location: str | None = None
    category: str | None = None
    auction_id: str | None = None

    def time_left(self, now: datetime) -> timedelta:
        return self.closes_at - now

    def differs_from(self, scraped: ScrapedLot) -> bool:
        """True if the bid state changed, which is what a snapshot records."""
        return (self.current_bid, self.bid_count, self.closes_at) != (
            scraped.current_bid,
            scraped.bid_count,
            scraped.closes_at,
        )
