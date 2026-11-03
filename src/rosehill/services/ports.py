"""What services need from storage. SQL implementations live in `rosehill.storage`."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from rosehill.domain.lot import ScrapedLot, StoredLot
from rosehill.domain.money import Money


@dataclass(frozen=True, slots=True)
class LotClosing:
    lot_id: int
    closed_at: datetime
    final_bid: Money
    bid_count: int
    title: str
    category: str | None


@dataclass(frozen=True, slots=True)
class ScrapeRun:
    id: int
    source: str
    kind: str
    started_at: datetime
    finished_at: datetime | None
    lots_seen: int
    lots_new: int
    lots_changed: int
    lots_closed: int
    error: str | None


class LotStore(Protocol):
    def find_by_source_ids(
        self, source: str, source_ids: Collection[str]
    ) -> dict[str, StoredLot]: ...

    def get(self, lot_id: int) -> StoredLot | None: ...

    def add(self, source: str, lot: ScrapedLot, seen_at: datetime) -> StoredLot: ...

    def update(self, lot_id: int, lot: ScrapedLot, seen_at: datetime) -> StoredLot: ...

    def touch(self, lot_ids: Collection[int], seen_at: datetime) -> None: ...

    def add_snapshot(self, lot_id: int, lot: ScrapedLot, observed_at: datetime) -> None: ...

    def close(self, closing: LotClosing, recorded_at: datetime) -> bool:
        """Mark the lot closed and record its final price. False if it was already closed."""
        ...

    def open_lots(self, source: str) -> list[StoredLot]: ...


class ScrapeRunLog(Protocol):
    def start(self, source: str, kind: str, started_at: datetime) -> int: ...

    def finish(
        self,
        run_id: int,
        finished_at: datetime,
        *,
        lots_seen: int,
        lots_new: int,
        lots_changed: int,
        lots_closed: int,
        error: str | None = None,
    ) -> None: ...

    def latest(self, source: str, kind: str | None = None) -> ScrapeRun | None: ...


class UnitOfWork(Protocol):
    """One transaction. Leaving the `with` block without `commit()` rolls back."""

    @property
    def lots(self) -> LotStore: ...

    @property
    def runs(self) -> ScrapeRunLog: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
