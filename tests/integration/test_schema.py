from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from rosehill.storage.db import UTCDateTime, make_engine
from rosehill.storage.schema import upgrade
from rosehill.storage.tables import Base


def test_migrations_create_exactly_the_declared_schema(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    upgrade(engine)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_upgrade_is_idempotent(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    upgrade(engine)
    upgrade(engine)
    assert "lots" in inspect(engine).get_table_names()


def test_sqlite_runs_with_foreign_keys_and_wal(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'nested' / 'db.sqlite'}")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"


def test_utc_datetime_rejects_naive_values() -> None:
    with pytest.raises(ValueError):
        UTCDateTime().process_bind_param(datetime(2026, 1, 1), dialect=None)  # type: ignore[arg-type]


def test_utc_datetime_returns_aware_utc() -> None:
    value = UTCDateTime().process_result_value(datetime(2026, 1, 1), dialect=None)  # type: ignore[arg-type]
    assert value == datetime(2026, 1, 1, tzinfo=UTC)
