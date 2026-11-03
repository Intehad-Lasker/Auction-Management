from datetime import UTC, datetime, timedelta

from rosehill.scraping.adapters.demo import DemoLotSource

START = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


def test_is_deterministic_for_a_seed() -> None:
    a = list(DemoLotSource(count=50, seed=1, now=lambda: START).fetch_active_lots())
    b = list(DemoLotSource(count=50, seed=1, now=lambda: START).fetch_active_lots())
    assert a == b


def test_generates_requested_number_of_open_lots_with_demo_urls() -> None:
    lots = list(DemoLotSource(count=200, seed=1, now=lambda: START).fetch_active_lots())
    assert len(lots) == 200
    assert all(lot.url.startswith("https://demo.invalid/") for lot in lots)
    assert len({lot.source_id for lot in lots}) == 200
    assert all(lot.closes_at > START for lot in lots)


def test_some_lots_close_within_each_dashboard_window() -> None:
    lots = list(DemoLotSource(count=500, seed=1, now=lambda: START).fetch_active_lots())
    for minutes in (30, 60, 120):
        assert any(lot.time_left(START) <= timedelta(minutes=minutes) for lot in lots)


def test_bids_never_decrease_as_time_passes() -> None:
    clock = Clock()
    source = DemoLotSource(count=100, seed=1, now=clock)
    before = {lot.source_id: lot for lot in source.fetch_active_lots()}
    clock.now += timedelta(minutes=20)
    after = {lot.source_id: lot for lot in source.fetch_lots(before)}
    for source_id, lot in after.items():
        assert lot.current_bid >= before[source_id].current_bid
        assert lot.bid_count >= before[source_id].bid_count


def test_lots_past_closing_are_reported_closed_and_left_out_of_active() -> None:
    clock = Clock()
    source = DemoLotSource(count=100, seed=1, now=clock)
    first = list(source.fetch_active_lots())
    soonest = min(first, key=lambda lot: lot.closes_at)
    clock.now = soonest.closes_at + timedelta(seconds=1)

    assert soonest.source_id not in {lot.source_id for lot in source.fetch_active_lots()}
    [closed] = source.fetch_lots([soonest.source_id])
    assert closed.is_closed


def test_name_is_demo() -> None:
    assert DemoLotSource(count=1).name == "demo"


def test_a_lot_keeps_its_identity_across_restarts() -> None:
    early = DemoLotSource(count=100, seed=1, now=lambda: START)
    lot = next(iter(early.fetch_active_lots()))
    later = DemoLotSource(count=100, seed=1, now=lambda: START + timedelta(hours=3))
    [again] = later.fetch_lots([lot.source_id])
    assert (again.title, again.closes_at) == (lot.title, lot.closes_at)


def test_lots_close_one_after_another_across_the_window() -> None:
    lots = list(DemoLotSource(count=480, seed=1, now=lambda: START).fetch_active_lots())
    closes = [lot.closes_at for lot in lots]
    assert closes == sorted(closes)
    assert closes[-1] - START <= timedelta(hours=8)


def test_unknown_ids_are_ignored() -> None:
    assert list(DemoLotSource(count=10).fetch_lots(["nope", "DEMO-abc"])) == []
