"""The closing-soon view: which open lots close within a window, filtered and sorted."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from rosehill.domain.lot import StoredLot
from rosehill.services.ports import LotQueries, ScrapeRun, UnitOfWork

WINDOWS = (30, 60, 120)


class SortKey(StrEnum):
    TIME_LEFT = "time_left"
    PRICE = "price"
    BIDS = "bids"


@dataclass(frozen=True, slots=True)
class DashboardFilters:
    window_minutes: int = 60
    search: str = ""
    category: str | None = None
    max_bids: int | None = None
    sort: SortKey = SortKey.TIME_LEFT
    descending: bool = False

    @property
    def search_terms(self) -> tuple[str, ...]:
        return tuple(self.search.split())

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> DashboardFilters:
        """Build filters from query parameters. Anything invalid falls back to its default."""
        default = cls()
        window = _int_or_none(params.get("window"))
        max_bids = _int_or_none(params.get("max_bids"))
        sort = params.get("sort", "")
        direction = params.get("dir", "")
        return cls(
            window_minutes=window if window in WINDOWS else default.window_minutes,
            search=" ".join(params.get("q", "").split()),
            category=params.get("category") or None,
            max_bids=max_bids if max_bids is not None and max_bids >= 0 else None,
            sort=SortKey(sort) if sort in SortKey._value2member_map_ else default.sort,
            descending=direction == "desc",
        )

    def to_params(self) -> dict[str, str]:
        params = {
            "window": str(self.window_minutes),
            "q": self.search,
            "category": self.category or "",
            "max_bids": "" if self.max_bids is None else str(self.max_bids),
            "sort": self.sort.value,
            "dir": "desc" if self.descending else "asc",
        }
        return params


@dataclass(frozen=True, slots=True)
class DashboardView:
    filters: DashboardFilters
    now: datetime
    rows: list[StoredLot]
    total: int
    categories: list[str]
    last_run: ScrapeRun | None = None
    source: str = ""
    windows: tuple[int, ...] = field(default=WINDOWS)


class DashboardService:
    def __init__(
        self,
        queries: LotQueries,
        uow: Callable[[], UnitOfWork],
        *,
        source: str,
        row_limit: int = 1000,
    ) -> None:
        self._queries = queries
        self._uow = uow
        self._source = source
        self._row_limit = row_limit

    def closing_soon(self, filters: DashboardFilters, now: datetime) -> DashboardView:
        rows, total = self._queries.closing_between(
            self._source,
            start=now,
            end=now + timedelta(minutes=filters.window_minutes),
            search_terms=filters.search_terms,
            category=filters.category,
            max_bids=filters.max_bids,
            sort=filters.sort.value,
            descending=filters.descending,
            limit=self._row_limit,
        )
        with self._uow() as tx:
            last_run = tx.runs.latest(self._source)
        return DashboardView(
            filters=filters,
            now=now,
            rows=rows,
            total=total,
            categories=self._queries.categories(self._source),
            last_run=last_run,
            source=self._source,
        )


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None
