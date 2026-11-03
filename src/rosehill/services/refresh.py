"""When to scrape: full sweeps on a slow cycle, lots near closing on faster ones."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from rosehill.domain.lot import StoredLot
from rosehill.scraping.ports import LotSource
from rosehill.services.ports import UnitOfWork
from rosehill.services.sync import SyncResult, SyncService

log = logging.getLogger(__name__)

_JITTER = timedelta(seconds=5)


@dataclass(frozen=True, slots=True)
class RefreshTier:
    """Lots closing within `within` are re-checked every `every`."""

    within: timedelta
    every: timedelta


@dataclass(frozen=True, slots=True)
class RefreshPolicy:
    full_sweep_every: timedelta
    retry_failed_sweep_after: timedelta
    tiers: tuple[RefreshTier, ...] = field(default=())

    def interval_for(self, time_left: timedelta) -> timedelta | None:
        tightest_first = sorted(self.tiers, key=lambda tier: tier.within)
        if not tightest_first:
            return None
        if time_left <= timedelta(0):
            return tightest_first[0].every  # past closing but not confirmed closed yet
        for tier in tightest_first:
            if time_left <= tier.within:
                return tier.every
        return None

    def due(self, lots: Iterable[StoredLot], now: datetime) -> list[StoredLot]:
        due: list[StoredLot] = []
        for lot in lots:
            interval = self.interval_for(lot.time_left(now))
            if interval is not None and now - lot.last_scraped_at >= interval - _JITTER:
                due.append(lot)
        return due

    def full_sweep_due(self, last_started: datetime | None, *, failed: bool, now: datetime) -> bool:
        if last_started is None:
            return True
        wait = self.retry_failed_sweep_after if failed else self.full_sweep_every
        return now - last_started >= wait - _JITTER


class RefreshService:
    """Runs scrapes against a `LotSource` and records each run."""

    FULL = "full"
    PARTIAL = "partial"

    def __init__(
        self,
        source: LotSource,
        sync: SyncService,
        uow: Callable[[], UnitOfWork],
        policy: RefreshPolicy,
        clock: Callable[[], datetime],
        close_grace: timedelta,
    ) -> None:
        self._source = source
        self._sync = sync
        self._uow = uow
        self._policy = policy
        self._clock = clock
        self._close_grace = close_grace

    def full_sweep(self) -> SyncResult:
        def run() -> SyncResult:
            lots = list(self._source.fetch_active_lots())
            result = self._sync.apply(self._source.name, lots)
            closed = self._sync.close_missing(
                self._source.name, {lot.source_id for lot in lots}, self._close_grace
            )
            return SyncResult(result.seen, result.new, result.changed, result.closed + closed)

        return self._recorded(self.FULL, run)

    def refresh_due(self) -> SyncResult | None:
        """Re-fetch lots whose tier interval has passed. None if nothing was due."""
        with self._uow() as tx:
            due = self._policy.due(tx.lots.open_lots(self._source.name), self._clock())
        if not due:
            return None
        ids = [lot.source_id for lot in due]
        return self._recorded(
            self.PARTIAL, lambda: self._sync.apply(self._source.name, self._source.fetch_lots(ids))
        )

    def tick(self) -> None:
        """One scheduler step: a full sweep if one is due, otherwise the due lots. Never raises."""
        try:
            with self._uow() as tx:
                last = tx.runs.latest(self._source.name, self.FULL)
            if self._policy.full_sweep_due(
                last.started_at if last else None,
                failed=bool(last and last.error),
                now=self._clock(),
            ):
                self.full_sweep()
            else:
                self.refresh_due()
        except Exception:
            log.exception("scheduled scrape failed")

    def _recorded(self, kind: str, run: Callable[[], SyncResult]) -> SyncResult:
        with self._uow() as tx:
            run_id = tx.runs.start(self._source.name, kind, self._clock())
            tx.commit()
        try:
            result = run()
        except Exception as exc:
            self._finish(run_id, SyncResult(), error=f"{type(exc).__name__}: {exc}")
            raise
        self._finish(run_id, result)
        log.info("%s scrape: %s", kind, result)
        return result

    def _finish(self, run_id: int, result: SyncResult, error: str | None = None) -> None:
        with self._uow() as tx:
            tx.runs.finish(
                run_id,
                self._clock(),
                lots_seen=result.seen,
                lots_new=result.new,
                lots_changed=result.changed,
                lots_closed=result.closed,
                error=error,
            )
            tx.commit()
