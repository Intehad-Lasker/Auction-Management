"""Turns batches of scraped lots into stored lots, bid snapshots, closing prices and events."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from rosehill.domain.lot import LotStatus, ScrapedLot, StoredLot
from rosehill.events import EventBus, LotClosed, LotUpdated
from rosehill.services.ports import LotClosing, UnitOfWork


@dataclass(frozen=True, slots=True)
class SyncResult:
    seen: int = 0
    new: int = 0
    changed: int = 0
    closed: int = 0

    def __str__(self) -> str:
        return (
            f"{self.seen} lots seen, {self.new} new, {self.changed} changed, {self.closed} closed"
        )


class SyncService:
    def __init__(
        self,
        uow: Callable[[], UnitOfWork],
        events: EventBus,
        clock: Callable[[], datetime],
    ) -> None:
        self._uow = uow
        self._events = events
        self._clock = clock

    def apply(self, source: str, lots: Iterable[ScrapedLot]) -> SyncResult:
        now = self._clock()
        batch = {lot.source_id: lot for lot in lots}  # last one wins if a source repeats a lot
        new = changed = closed = 0
        pending: list[object] = []
        unchanged: list[int] = []

        with self._uow() as tx:
            existing = tx.lots.find_by_source_ids(source, batch)
            for source_id, lot in batch.items():
                previous = existing.get(source_id)
                if previous is None:
                    stored = tx.lots.add(source, lot, now)
                    tx.lots.add_snapshot(stored.id, lot, now)
                    pending.append(LotUpdated(stored, is_new=True))
                    new += 1
                elif _same_listing(previous, lot):
                    stored = previous
                    unchanged.append(previous.id)
                else:
                    stored = tx.lots.update(previous.id, lot, now)
                    if previous.differs_from(lot):
                        tx.lots.add_snapshot(stored.id, lot, now)
                    pending.append(LotUpdated(stored, is_new=False))
                    changed += 1

                if lot.is_closed and stored.status is LotStatus.OPEN:
                    closing = LotClosing(
                        stored.id,
                        lot.closes_at,
                        lot.current_bid,
                        lot.bid_count,
                        lot.title,
                        lot.category,
                    )
                    if tx.lots.close(closing, now):
                        pending.append(LotClosed(stored, closed_at=lot.closes_at))
                        closed += 1

            tx.lots.touch(unchanged, now)
            tx.commit()

        self._publish(pending)
        return SyncResult(seen=len(batch), new=new, changed=changed, closed=closed)

    def close_missing(self, source: str, active_ids: Collection[str], grace: timedelta) -> int:
        """Close lots a full sweep no longer lists once they are `grace` past closing.

        Their last observed bid becomes the closing price.
        """
        now = self._clock()
        active = set(active_ids)
        pending: list[object] = []
        with self._uow() as tx:
            for lot in tx.lots.open_lots(source):
                if lot.source_id in active or lot.closes_at > now - grace:
                    continue
                closing = LotClosing(
                    lot.id, lot.closes_at, lot.current_bid, lot.bid_count, lot.title, lot.category
                )
                if tx.lots.close(closing, now):
                    pending.append(LotClosed(lot, closed_at=lot.closes_at))
            tx.commit()
        self._publish(pending)
        return len(pending)

    def _publish(self, events: list[object]) -> None:
        for event in events:
            self._events.publish(event)


def _same_listing(stored: StoredLot, scraped: ScrapedLot) -> bool:
    return not stored.differs_from(scraped) and (
        stored.title,
        stored.category,
        stored.url,
        stored.photos,
        stored.pickup_location,
        stored.auction_id,
    ) == (
        scraped.title,
        scraped.category,
        scraped.url,
        scraped.photos,
        scraped.pickup_location,
        scraped.auction_id,
    )
