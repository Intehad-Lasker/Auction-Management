from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from rosehill.config import Settings
from rosehill.container import build_container
from rosehill.domain.lot import ScrapedLot
from rosehill.domain.money import Money
from rosehill.storage.db import make_engine, make_session_factory
from rosehill.storage.repositories import SqlUnitOfWork
from rosehill.storage.tables import Base
from rosehill.web.app import create_app

NOW = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield make_session_factory(engine)
    engine.dispose()


@pytest.fixture
def uow(session_factory: sessionmaker[Session]) -> Callable[[], SqlUnitOfWork]:
    return lambda: SqlUnitOfWork(session_factory)


def scraped(source_id: str = "L1", **overrides: object) -> ScrapedLot:
    fields: dict[str, object] = {
        "source_id": source_id,
        "title": f"Lot {source_id}",
        "current_bid": Money(1000),
        "bid_count": 2,
        "closes_at": datetime(2026, 11, 3, 19, 0, tzinfo=UTC),
        "url": f"https://demo.invalid/lots/{source_id}",
        "photos": ("https://demo.invalid/a.jpg",),
        "pickup_location": "Burlington warehouse",
        "category": "Tools",
    }
    fields.update(overrides)
    return ScrapedLot(**fields)  # type: ignore[arg-type]


class FixedSource:
    """Serves a fixed set of lots so page assertions are exact."""

    name = "demo"

    def __init__(self) -> None:
        self.lots = [
            scraped(
                "a",
                title="Dyson V8 vacuum",
                category="Appliances",
                current_bid=Money(9000),
                bid_count=12,
                closes_at=NOW + timedelta(minutes=4),
            ),
            scraped(
                "b",
                title="DeWalt drill kit",
                category="Tools",
                current_bid=Money(0),
                bid_count=0,
                closes_at=NOW + timedelta(minutes=40),
            ),
            scraped(
                "c",
                title="Oak dining table",
                category="Furniture",
                current_bid=Money(15000),
                bid_count=20,
                closes_at=NOW + timedelta(minutes=100),
            ),
        ]

    def fetch_active_lots(self):  # type: ignore[no-untyped-def]
        return iter(self.lots)

    def fetch_lots(self, source_ids):  # type: ignore[no-untyped-def]
        return iter(lot for lot in self.lots if lot.source_id in source_ids)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'web.db'}")
    container = build_container(settings, clock=lambda: NOW, source=FixedSource())  # type: ignore[arg-type]
    container.upgrade_database()
    container.refresh.full_sweep()
    with TestClient(create_app(container, run_scheduler=False)) as test_client:
        yield test_client
