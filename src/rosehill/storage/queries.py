"""SQL implementation of the read-side `LotQueries` port."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, sessionmaker

from rosehill.domain.lot import LotStatus, StoredLot
from rosehill.storage.repositories import to_stored_lot
from rosehill.storage.tables import LotRow

_SORT_COLUMNS = {
    "time_left": LotRow.closes_at,
    "price": LotRow.current_bid_cents,
    "bids": LotRow.bid_count,
}


class SqlLotQueries:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def closing_between(
        self,
        source: str,
        *,
        start: datetime,
        end: datetime,
        search_terms: Sequence[str],
        category: str | None,
        max_bids: int | None,
        sort: str,
        descending: bool,
        limit: int,
    ) -> tuple[list[StoredLot], int]:
        conditions: list[ColumnElement[bool]] = [
            LotRow.source == source,
            LotRow.status == LotStatus.OPEN.value,
            LotRow.closes_at >= start,
            LotRow.closes_at < end,
        ]
        for term in search_terms:
            conditions.append(LotRow.title.icontains(term, autoescape=True))
        if category is not None:
            conditions.append(LotRow.category == category)
        if max_bids is not None:
            conditions.append(LotRow.bid_count <= max_bids)

        column = _SORT_COLUMNS.get(sort, LotRow.closes_at)
        order = column.desc() if descending else column.asc()
        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(LotRow).where(*conditions))
            rows = session.scalars(
                select(LotRow).where(*conditions).order_by(order, LotRow.closes_at).limit(limit)
            )
            return [to_stored_lot(row) for row in rows], total or 0

    def categories(self, source: str) -> list[str]:
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(LotRow.category)
                    .where(LotRow.source == source, LotRow.category.is_not(None))
                    .distinct()
                    .order_by(LotRow.category)
                )
            )
