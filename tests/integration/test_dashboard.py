from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from rosehill.domain.money import Money
from rosehill.services.dashboard import DashboardFilters, DashboardService, SortKey
from rosehill.services.ports import LotClosing
from rosehill.storage.queries import SqlLotQueries
from rosehill.storage.repositories import SqlUnitOfWork

from .conftest import NOW, scraped


def seed(uow: Callable[[], SqlUnitOfWork]) -> None:
    lots = [
        scraped(
            "a",
            title="Dyson V8 vacuum",
            category="Appliances",
            current_bid=Money(9000),
            bid_count=12,
            closes_at=NOW + timedelta(minutes=10),
        ),
        scraped(
            "b",
            title="DeWalt drill kit",
            category="Tools",
            current_bid=Money(4000),
            bid_count=0,
            closes_at=NOW + timedelta(minutes=25),
        ),
        scraped(
            "c",
            title="Dyson hair dryer",
            category="Appliances",
            current_bid=Money(2000),
            bid_count=3,
            closes_at=NOW + timedelta(minutes=50),
        ),
        scraped(
            "d",
            title="Oak table",
            category="Furniture",
            current_bid=Money(15000),
            bid_count=20,
            closes_at=NOW + timedelta(minutes=100),
        ),
        scraped(
            "e",
            title="Far away lot",
            category="Tools",
            current_bid=Money(100),
            bid_count=0,
            closes_at=NOW + timedelta(hours=5),
        ),
        scraped(
            "gone", title="Already closed", category="Tools", closes_at=NOW - timedelta(minutes=1)
        ),
        scraped(
            "closed", title="Closed early", category="Tools", closes_at=NOW + timedelta(minutes=5)
        ),
    ]
    with uow() as tx:
        for lot in lots:
            stored = tx.lots.add("demo", lot, NOW)
            if lot.source_id == "closed":
                tx.lots.close(LotClosing(stored.id, NOW, Money(1), 1, "x", None), NOW)
        tx.lots.add("other-source", scraped("z", closes_at=NOW + timedelta(minutes=5)), NOW)
        tx.commit()


def service(
    session_factory: sessionmaker[Session], uow: Callable[[], SqlUnitOfWork]
) -> DashboardService:
    return DashboardService(SqlLotQueries(session_factory), uow, source="demo", row_limit=100)


def ids(view: object) -> list[str]:
    return [lot.source_id for lot in view.rows]  # type: ignore[attr-defined]


def run(
    session_factory: sessionmaker[Session],
    uow: Callable[[], SqlUnitOfWork],
    now: datetime = NOW,
    **filters: object,
) -> object:
    seed(uow)
    return service(session_factory, uow).closing_soon(DashboardFilters(**filters), now)  # type: ignore[arg-type]


def test_window_includes_open_lots_from_this_source_only(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    assert ids(run(session_factory, uow, window_minutes=30)) == ["a", "b"]
    view = service(session_factory, uow).closing_soon(DashboardFilters(window_minutes=120), NOW)
    assert ids(view) == ["a", "b", "c", "d"]


def test_search_matches_every_word_case_insensitively(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    assert ids(run(session_factory, uow, window_minutes=120, search="dyson VAC")) == ["a"]


def test_category_filter(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    assert ids(run(session_factory, uow, window_minutes=120, category="Appliances")) == ["a", "c"]


def test_low_bid_filter(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    assert ids(run(session_factory, uow, window_minutes=120, max_bids=3)) == ["b", "c"]
    view = service(session_factory, uow).closing_soon(
        DashboardFilters(window_minutes=120, max_bids=0), NOW
    )
    assert ids(view) == ["b"]


def test_sorting(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    seed(uow)
    svc = service(session_factory, uow)

    def order(sort: SortKey, descending: bool) -> list[str]:
        f = DashboardFilters(window_minutes=120, sort=sort, descending=descending)
        return ids(svc.closing_soon(f, NOW))

    assert order(SortKey.PRICE, False) == ["c", "b", "a", "d"]
    assert order(SortKey.PRICE, True) == ["d", "a", "b", "c"]
    assert order(SortKey.BIDS, False) == ["b", "c", "a", "d"]
    assert order(SortKey.TIME_LEFT, True) == ["d", "c", "b", "a"]


def test_search_wildcards_are_literal(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    assert ids(run(session_factory, uow, window_minutes=120, search="%")) == []
    view = service(session_factory, uow).closing_soon(
        DashboardFilters(window_minutes=120, search="_"), NOW
    )
    assert ids(view) == []


def test_view_reports_total_categories_and_row_limit(session_factory, uow) -> None:  # type: ignore[no-untyped-def]
    seed(uow)
    svc = DashboardService(SqlLotQueries(session_factory), uow, source="demo", row_limit=2)
    view = svc.closing_soon(DashboardFilters(window_minutes=120), NOW)
    assert view.total == 4
    assert len(view.rows) == 2
    assert view.categories == ["Appliances", "Furniture", "Tools"]
