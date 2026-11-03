from datetime import UTC, datetime, timedelta

from rosehill.domain.lot import LotStatus, StoredLot
from rosehill.domain.money import Money
from rosehill.services.refresh import RefreshPolicy, RefreshTier

NOW = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)
POLICY = RefreshPolicy(
    full_sweep_every=timedelta(minutes=60),
    retry_failed_sweep_after=timedelta(minutes=5),
    tiers=(
        RefreshTier(within=timedelta(minutes=120), every=timedelta(minutes=5)),
        RefreshTier(within=timedelta(minutes=15), every=timedelta(minutes=1)),
    ),
)


def lot(closes_in: timedelta, scraped_ago: timedelta, lot_id: int = 1) -> StoredLot:
    return StoredLot(
        id=lot_id,
        source="demo",
        source_id=f"L{lot_id}",
        title="x",
        current_bid=Money(0),
        bid_count=0,
        closes_at=NOW + closes_in,
        status=LotStatus.OPEN,
        url="https://demo.invalid/x",
        first_seen_at=NOW - timedelta(days=1),
        last_scraped_at=NOW - scraped_ago,
    )


def test_tiers_are_matched_tightest_first_regardless_of_order() -> None:
    assert POLICY.interval_for(timedelta(minutes=10)) == timedelta(minutes=1)
    assert POLICY.interval_for(timedelta(minutes=90)) == timedelta(minutes=5)
    assert POLICY.interval_for(timedelta(hours=5)) is None


def test_overdue_lots_use_the_fastest_interval() -> None:
    assert POLICY.interval_for(timedelta(minutes=-3)) == timedelta(minutes=1)


def test_due_selects_lots_whose_interval_has_passed() -> None:
    lots = [
        lot(timedelta(minutes=10), timedelta(seconds=70), lot_id=1),  # 1-min tier, due
        lot(timedelta(minutes=10), timedelta(seconds=20), lot_id=2),  # 1-min tier, fresh
        lot(timedelta(minutes=60), timedelta(minutes=6), lot_id=3),  # 5-min tier, due
        lot(timedelta(minutes=60), timedelta(minutes=2), lot_id=4),  # 5-min tier, fresh
        lot(timedelta(hours=5), timedelta(minutes=50), lot_id=5),  # left to the full sweep
        lot(timedelta(minutes=-2), timedelta(minutes=2), lot_id=6),  # past close, unconfirmed
    ]
    assert [x.id for x in POLICY.due(lots, NOW)] == [1, 3, 6]


def test_due_allows_a_few_seconds_of_scheduler_jitter() -> None:
    assert POLICY.due([lot(timedelta(minutes=10), timedelta(seconds=57))], NOW)


def test_full_sweep_is_due_when_never_run_or_interval_passed() -> None:
    assert POLICY.full_sweep_due(None, failed=False, now=NOW)
    assert POLICY.full_sweep_due(NOW - timedelta(minutes=61), failed=False, now=NOW)
    assert not POLICY.full_sweep_due(NOW - timedelta(minutes=30), failed=False, now=NOW)


def test_failed_sweep_is_retried_sooner() -> None:
    assert POLICY.full_sweep_due(NOW - timedelta(minutes=6), failed=True, now=NOW)
    assert not POLICY.full_sweep_due(NOW - timedelta(minutes=2), failed=True, now=NOW)
