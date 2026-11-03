from collections.abc import Callable, Collection, Iterator
from datetime import datetime, timedelta

import pytest

from rosehill.domain.lot import ScrapedLot
from rosehill.events import EventBus
from rosehill.scraping.adapters.demo import DemoLotSource
from rosehill.services.refresh import RefreshPolicy, RefreshService, RefreshTier
from rosehill.services.sync import SyncService
from rosehill.storage.repositories import SqlUnitOfWork

from .conftest import NOW

POLICY = RefreshPolicy(
    full_sweep_every=timedelta(minutes=60),
    retry_failed_sweep_after=timedelta(minutes=5),
    tiers=(
        RefreshTier(within=timedelta(minutes=120), every=timedelta(minutes=5)),
        RefreshTier(within=timedelta(minutes=15), every=timedelta(minutes=1)),
    ),
)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class BrokenSource:
    name = "broken"

    def fetch_active_lots(self) -> Iterator[ScrapedLot]:
        raise ConnectionError("site down")

    def fetch_lots(self, source_ids: Collection[str]) -> Iterator[ScrapedLot]:
        raise ConnectionError("site down")


class CountingSource(DemoLotSource):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.full_calls = 0
        self.partial_ids: list[list[str]] = []

    def fetch_active_lots(self) -> Iterator[ScrapedLot]:
        self.full_calls += 1
        return super().fetch_active_lots()

    def fetch_lots(self, source_ids: Collection[str]) -> Iterator[ScrapedLot]:
        self.partial_ids.append(list(source_ids))
        return super().fetch_lots(source_ids)


def service(source: object, uow: Callable[[], SqlUnitOfWork], clock: Clock) -> RefreshService:
    sync = SyncService(uow, EventBus(), clock)
    return RefreshService(source, sync, uow, POLICY, clock, close_grace=timedelta(minutes=5))  # type: ignore[arg-type]


def test_full_sweep_stores_lots_and_records_the_run(
    uow: Callable[[], SqlUnitOfWork],
) -> None:
    clock = Clock()
    result = service(DemoLotSource(count=100, now=clock), uow, clock).full_sweep()
    assert result.new == 100
    with uow() as tx:
        run = tx.runs.latest("demo", "full")
        assert len(tx.lots.open_lots("demo")) == 100
    assert run is not None and run.lots_new == 100 and run.error is None
    assert run.finished_at is not None


def test_failed_sweep_is_recorded_and_reraised(uow: Callable[[], SqlUnitOfWork]) -> None:
    clock = Clock()
    with pytest.raises(ConnectionError):
        service(BrokenSource(), uow, clock).full_sweep()
    with uow() as tx:
        run = tx.runs.latest("broken")
    assert run is not None and run.error == "ConnectionError: site down"


def test_tick_never_raises(uow: Callable[[], SqlUnitOfWork]) -> None:
    clock = Clock()
    service(BrokenSource(), uow, clock).tick()


def test_tick_runs_a_full_sweep_first_then_only_due_lots(
    uow: Callable[[], SqlUnitOfWork],
) -> None:
    clock = Clock()
    source = CountingSource(count=200, now=clock)
    refresher = service(source, uow, clock)

    refresher.tick()
    assert source.full_calls == 1

    clock.now += timedelta(minutes=2)
    refresher.tick()
    assert source.full_calls == 1
    refreshed = source.partial_ids[-1]
    assert refreshed  # lots within 15 minutes are due after a minute
    with uow() as tx:
        lots = {lot.source_id: lot for lot in tx.lots.open_lots("demo")}
    assert all(
        lots[i].time_left(clock.now) <= timedelta(minutes=15) for i in refreshed if i in lots
    )


def test_lots_closing_between_sweeps_get_their_closing_price(
    uow: Callable[[], SqlUnitOfWork],
) -> None:
    clock = Clock()
    refresher = service(DemoLotSource(count=200, now=clock), uow, clock)
    refresher.full_sweep()
    for _ in range(20):
        clock.now += timedelta(minutes=1)
        refresher.tick()
    with uow() as tx:
        open_ids = {lot.source_id for lot in tx.lots.open_lots("demo")}
        last_partial = tx.runs.latest("demo", "partial")
    assert last_partial is not None
    assert all(  # nothing that closed in those 20 minutes is still open
        lot.closes_at > clock.now - timedelta(minutes=1)
        for lot in DemoLotSource(count=200, now=clock).fetch_lots(open_ids)
    )
