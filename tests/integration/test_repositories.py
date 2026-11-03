from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import func, select

from rosehill.domain.lot import LotStatus
from rosehill.domain.money import Money
from rosehill.services.ports import LotClosing
from rosehill.storage.repositories import SqlUnitOfWork
from rosehill.storage.tables import LotClosingRow, LotSnapshotRow

from .conftest import NOW, scraped

UowFactory = Callable[[], SqlUnitOfWork]


def test_add_then_find_round_trips_every_field(uow: UowFactory) -> None:
    with uow() as tx:
        added = tx.lots.add("demo", scraped("L1"), NOW)
        tx.commit()
    with uow() as tx:
        found = tx.lots.find_by_source_ids("demo", ["L1", "missing"])
    assert list(found) == ["L1"]
    lot = found["L1"]
    assert lot == added
    assert lot.status is LotStatus.OPEN
    assert lot.current_bid == Money(1000)
    assert lot.photos == ("https://demo.invalid/a.jpg",)
    assert lot.closes_at.tzinfo is not None
    assert lot.first_seen_at == lot.last_scraped_at == NOW


def test_same_source_id_from_different_sources_are_separate_lots(uow: UowFactory) -> None:
    with uow() as tx:
        tx.lots.add("demo", scraped("L1"), NOW)
        tx.lots.add("rosehill", scraped("L1"), NOW)
        tx.commit()
    with uow() as tx:
        assert len(tx.lots.find_by_source_ids("demo", ["L1"])) == 1
        assert len(tx.lots.open_lots("rosehill")) == 1


def test_update_replaces_values_and_photos(uow: UowFactory) -> None:
    later = NOW + timedelta(minutes=5)
    with uow() as tx:
        lot = tx.lots.add("demo", scraped("L1"), NOW)
        updated = tx.lots.update(
            lot.id, scraped("L1", current_bid=Money(2500), photos=("x.jpg", "y.jpg")), later
        )
        tx.commit()
    assert updated.current_bid == Money(2500)
    assert updated.photos == ("x.jpg", "y.jpg")
    assert updated.first_seen_at == NOW
    assert updated.last_scraped_at == later


def test_find_handles_more_ids_than_one_query_allows(uow: UowFactory) -> None:
    ids = [f"L{i}" for i in range(1200)]
    with uow() as tx:
        for source_id in ids:
            tx.lots.add("demo", scraped(source_id), NOW)
        tx.commit()
    with uow() as tx:
        assert len(tx.lots.find_by_source_ids("demo", ids)) == 1200


def test_touch_updates_last_scraped_only(uow: UowFactory) -> None:
    later = NOW + timedelta(minutes=1)
    with uow() as tx:
        lot = tx.lots.add("demo", scraped("L1"), NOW)
        tx.lots.touch([lot.id], later)
        tx.commit()
    with uow() as tx:
        stored = tx.lots.get(lot.id)
    assert stored is not None
    assert stored.last_scraped_at == later


def test_close_records_the_final_price_once(uow: UowFactory, session_factory) -> None:  # type: ignore[no-untyped-def]
    with uow() as tx:
        lot = tx.lots.add("demo", scraped("L1"), NOW)
        closing = LotClosing(lot.id, lot.closes_at, Money(4200), 9, lot.title, lot.category)
        assert tx.lots.close(closing, NOW) is True
        assert tx.lots.close(closing, NOW) is False
        tx.commit()
    with uow() as tx:
        assert tx.lots.open_lots("demo") == []
        stored = tx.lots.get(lot.id)
    assert stored is not None and stored.status is LotStatus.CLOSED
    with session_factory() as session:
        row = session.scalars(select(LotClosingRow)).one()
    assert (row.final_bid_cents, row.bid_count) == (4200, 9)


def test_snapshots_are_appended(uow: UowFactory, session_factory) -> None:  # type: ignore[no-untyped-def]
    with uow() as tx:
        lot = tx.lots.add("demo", scraped("L1"), NOW)
        tx.lots.add_snapshot(lot.id, scraped("L1"), NOW)
        tx.lots.add_snapshot(lot.id, scraped("L1", current_bid=Money(1100)), NOW)
        tx.commit()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(LotSnapshotRow)) == 2


def test_leaving_without_commit_rolls_back(uow: UowFactory) -> None:
    with uow() as tx:
        tx.lots.add("demo", scraped("L1"), NOW)
    with uow() as tx:
        assert tx.lots.open_lots("demo") == []


def test_open_lots_are_ordered_by_closing_time(uow: UowFactory) -> None:
    with uow() as tx:
        tx.lots.add("demo", scraped("late", closes_at=NOW + timedelta(hours=2)), NOW)
        tx.lots.add("demo", scraped("soon", closes_at=NOW + timedelta(minutes=5)), NOW)
        tx.commit()
    with uow() as tx:
        assert [lot.source_id for lot in tx.lots.open_lots("demo")] == ["soon", "late"]


def test_scrape_run_log(uow: UowFactory) -> None:
    with uow() as tx:
        first = tx.runs.start("demo", "full", NOW)
        tx.runs.finish(
            first,
            NOW + timedelta(seconds=3),
            lots_seen=5,
            lots_new=5,
            lots_changed=0,
            lots_closed=0,
        )
        tx.runs.start("demo", "partial", NOW + timedelta(minutes=1))
        tx.commit()
    with uow() as tx:
        latest_full = tx.runs.latest("demo", "full")
        latest_any = tx.runs.latest("demo")
    assert latest_full is not None and latest_full.lots_seen == 5
    assert latest_any is not None and latest_any.kind == "partial"
    assert latest_any.finished_at is None
