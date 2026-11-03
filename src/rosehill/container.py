"""Composition root: the one place that picks concrete implementations and wires them up."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from rosehill.config import Settings
from rosehill.events import EventBus
from rosehill.scraping.ports import LotSource
from rosehill.scraping.registry import build_lot_source
from rosehill.services.refresh import RefreshPolicy, RefreshService, RefreshTier
from rosehill.services.sync import SyncService
from rosehill.storage.db import make_engine, make_session_factory
from rosehill.storage.http_cache import SqlResponseCache
from rosehill.storage.repositories import SqlUnitOfWork
from rosehill.storage.schema import upgrade


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    clock: Callable[[], datetime]
    events: EventBus
    source: LotSource
    sync: SyncService
    refresh: RefreshService

    def uow(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self.session_factory)

    def upgrade_database(self) -> None:
        upgrade(self.engine)


def refresh_policy(settings: Settings) -> RefreshPolicy:
    return RefreshPolicy(
        full_sweep_every=timedelta(minutes=settings.full_sweep_minutes),
        retry_failed_sweep_after=timedelta(minutes=5),
        tiers=(
            RefreshTier(
                within=timedelta(minutes=settings.soon_within_minutes),
                every=timedelta(minutes=settings.soon_every_minutes),
            ),
            RefreshTier(
                within=timedelta(minutes=settings.imminent_within_minutes),
                every=timedelta(minutes=settings.imminent_every_minutes),
            ),
        ),
    )


def build_container(
    settings: Settings,
    *,
    clock: Callable[[], datetime] = utc_now,
    source: LotSource | None = None,
) -> Container:
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    events = EventBus()

    def uow() -> SqlUnitOfWork:
        return SqlUnitOfWork(session_factory)

    lot_source = source or build_lot_source(settings, SqlResponseCache(session_factory))
    sync = SyncService(uow, events, clock)
    refresh = RefreshService(
        lot_source,
        sync,
        uow,
        refresh_policy(settings),
        clock,
        close_grace=timedelta(minutes=settings.close_grace_minutes),
    )
    return Container(settings, engine, session_factory, clock, events, lot_source, sync, refresh)
