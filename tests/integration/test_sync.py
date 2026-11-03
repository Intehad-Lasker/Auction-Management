from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from rosehill.domain.lot import LotStatus
from rosehill.domain.money import Money
from rosehill.events import EventBus, LotClosed, LotUpdated
from rosehill.services.sync import SyncService
from rosehill.storage.repositories import SqlUnitOfWork
from rosehill.storage.tables import LotClosingRow, LotSnapshotRow

from .conftest import NOW, scraped


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def events() -> tuple[EventBus, list[object]]:
    bus = EventBus()
    seen: list[object] = []
    bus.subscribe(LotUpdated, seen.append)
    bus.subscribe(LotClosed, seen.append)
    return bus, seen


@pytest.fixture
def sync(
    uow: Callable[[], SqlUnitOfWork], events: tuple[EventBus, list[object]], clock: Clock
) -> SyncService:
    return SyncService(uow, events[0], clock)


def count(session_factory: sessionmaker[Session], table: type) -> int:
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(table)) or 0


def test_new_lots_are_stored_with_a_first_snapshot(
    sync: SyncService, session_factory: sessionmaker[Session], events: tuple[EventBus, list[object]]
) -> None:
    result = sync.apply("demo", [scraped("A"), scraped("B")])
    assert (result.seen, result.new, result.changed, result.closed) == (2, 2, 0, 0)
    assert count(session_factory, LotSnapshotRow) == 2
    assert all(isinstance(e, LotUpdated) and e.is_new for e in events[1])


def test_unchanged_lots_only_update_last_scraped(
    sync: SyncService,
    session_factory: sessionmaker[Session],
    uow: Callable[[], SqlUnitOfWork],
    clock: Clock,
    events: tuple[EventBus, list[object]],
) -> None:
    sync.apply("demo", [scraped("A")])
    events[1].clear()
    clock.now += timedelta(minutes=5)
    result = sync.apply("demo", [scraped("A")])
    assert (result.new, result.changed) == (0, 0)
    assert count(session_factory, LotSnapshotRow) == 1
    assert events[1] == []
    with uow() as tx:
        assert tx.lots.find_by_source_ids("demo", ["A"])["A"].last_scraped_at == clock.now


def test_bid_changes_update_the_lot_and_add_a_snapshot(
    sync: SyncService, session_factory: sessionmaker[Session], events: tuple[EventBus, list[object]]
) -> None:
    sync.apply("demo", [scraped("A")])
    result = sync.apply("demo", [scraped("A", current_bid=Money(5000), bid_count=7)])
    assert result.changed == 1
    assert count(session_factory, LotSnapshotRow) == 2
    last = events[1][-1]
    assert isinstance(last, LotUpdated) and not last.is_new
    assert last.lot.current_bid == Money(5000)


def test_title_change_updates_without_a_snapshot(
    sync: SyncService, session_factory: sessionmaker[Session]
) -> None:
    sync.apply("demo", [scraped("A")])
    result = sync.apply("demo", [scraped("A", title="Corrected title")])
    assert result.changed == 1
    assert count(session_factory, LotSnapshotRow) == 1


def test_closed_lots_record_their_final_price_once(
    sync: SyncService,
    session_factory: sessionmaker[Session],
    events: tuple[EventBus, list[object]],
) -> None:
    sync.apply("demo", [scraped("A")])
    final = scraped("A", current_bid=Money(8800), bid_count=12, is_closed=True)
    assert sync.apply("demo", [final]).closed == 1
    assert sync.apply("demo", [final]).closed == 0
    with session_factory() as session:
        row = session.scalars(select(LotClosingRow)).one()
    assert (row.final_bid_cents, row.bid_count) == (8800, 12)
    assert sum(isinstance(e, LotClosed) for e in events[1]) == 1


def test_a_lot_first_seen_already_closed_is_still_recorded(
    sync: SyncService, session_factory: sessionmaker[Session]
) -> None:
    assert sync.apply("demo", [scraped("A", is_closed=True)]).closed == 1
    assert count(session_factory, LotClosingRow) == 1


def test_duplicate_ids_in_one_batch_count_once(sync: SyncService) -> None:
    result = sync.apply("demo", [scraped("A"), scraped("A", current_bid=Money(2000))])
    assert (result.seen, result.new) == (1, 1)


def test_close_missing_closes_overdue_lots_absent_from_a_full_sweep(
    sync: SyncService,
    uow: Callable[[], SqlUnitOfWork],
    session_factory: sessionmaker[Session],
    clock: Clock,
) -> None:
    sync.apply(
        "demo",
        [
            scraped("gone", closes_at=NOW + timedelta(minutes=1), current_bid=Money(3100)),
            scraped("still-listed", closes_at=NOW + timedelta(minutes=1)),
            scraped("later", closes_at=NOW + timedelta(hours=3)),
        ],
    )
    clock.now = NOW + timedelta(minutes=10)
    closed = sync.close_missing("demo", active_ids={"still-listed"}, grace=timedelta(minutes=5))
    assert closed == 1
    with uow() as tx:
        statuses = {lot.source_id: lot.status for lot in tx.lots.open_lots("demo")}
    assert statuses == {"still-listed": LotStatus.OPEN, "later": LotStatus.OPEN}
    with session_factory() as session:
        assert session.scalars(select(LotClosingRow.final_bid_cents)).one() == 3100


def test_close_missing_respects_the_grace_period(sync: SyncService, clock: Clock) -> None:
    sync.apply("demo", [scraped("A", closes_at=NOW + timedelta(minutes=1))])
    clock.now = NOW + timedelta(minutes=3)
    assert sync.close_missing("demo", active_ids=set(), grace=timedelta(minutes=5)) == 0


def test_events_are_published_after_commit(uow: Callable[[], SqlUnitOfWork], clock: Clock) -> None:
    bus = EventBus()
    stored_when_notified: list[bool] = []

    def check(event: LotUpdated) -> None:
        with uow() as tx:
            stored_when_notified.append(tx.lots.get(event.lot.id) is not None)

    bus.subscribe(LotUpdated, check)
    SyncService(uow, bus, clock).apply("demo", [scraped("A")])
    assert stored_when_notified == [True]
