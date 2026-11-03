from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session, sessionmaker

from rosehill.domain.lot import ScrapedLot
from rosehill.domain.money import Money
from rosehill.storage.db import make_engine, make_session_factory
from rosehill.storage.repositories import SqlUnitOfWork
from rosehill.storage.tables import Base

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
