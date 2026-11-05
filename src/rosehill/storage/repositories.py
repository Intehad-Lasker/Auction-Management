"""SQLAlchemy implementations of the service ports."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from types import TracebackType
from typing import Any, Self

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from rosehill.domain.lot import LotStatus, ScrapedLot, StoredLot
from rosehill.domain.money import Money
from rosehill.services.ports import LotClosing, ScrapeRun
from rosehill.storage.tables import (
    LotClosingRow,
    LotPhotoRow,
    LotRow,
    LotSnapshotRow,
    ScrapeRunRow,
    SettingRow,
)

_IN_CHUNK = 500  # stay well under SQLite's bound-parameter limit


def to_stored_lot(row: LotRow) -> StoredLot:
    return StoredLot(
        id=row.id,
        source=row.source,
        source_id=row.source_id,
        title=row.title,
        current_bid=Money(row.current_bid_cents),
        bid_count=row.bid_count,
        closes_at=row.closes_at,
        status=LotStatus(row.status),
        url=row.url,
        first_seen_at=row.first_seen_at,
        last_scraped_at=row.last_scraped_at,
        photos=tuple(photo.url for photo in row.photos),
        pickup_location=row.pickup_location,
        category=row.category,
        auction_id=row.auction_id,
    )


class SqlLotStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_source_ids(self, source: str, source_ids: Collection[str]) -> dict[str, StoredLot]:
        ids = list(source_ids)
        found: dict[str, StoredLot] = {}
        for start in range(0, len(ids), _IN_CHUNK):
            chunk = ids[start : start + _IN_CHUNK]
            rows = self._session.scalars(
                select(LotRow).where(LotRow.source == source, LotRow.source_id.in_(chunk))
            )
            found.update({row.source_id: to_stored_lot(row) for row in rows})
        return found

    def get(self, lot_id: int) -> StoredLot | None:
        row = self._session.get(LotRow, lot_id)
        return None if row is None else to_stored_lot(row)

    def add(self, source: str, lot: ScrapedLot, seen_at: datetime) -> StoredLot:
        row = LotRow(
            source=source,
            source_id=lot.source_id,
            status=LotStatus.OPEN.value,
            first_seen_at=seen_at,
        )
        self._apply(row, lot, seen_at)
        self._session.add(row)
        self._session.flush()
        return to_stored_lot(row)

    def update(self, lot_id: int, lot: ScrapedLot, seen_at: datetime) -> StoredLot:
        row = self._session.get_one(LotRow, lot_id)
        self._apply(row, lot, seen_at)
        self._session.flush()
        return to_stored_lot(row)

    def touch(self, lot_ids: Collection[int], seen_at: datetime) -> None:
        ids = list(lot_ids)
        for start in range(0, len(ids), _IN_CHUNK):
            self._session.execute(
                update(LotRow)
                .where(LotRow.id.in_(ids[start : start + _IN_CHUNK]))
                .values(last_scraped_at=seen_at)
            )

    def add_snapshot(self, lot_id: int, lot: ScrapedLot, observed_at: datetime) -> None:
        self._session.add(
            LotSnapshotRow(
                lot_id=lot_id,
                observed_at=observed_at,
                current_bid_cents=lot.current_bid.cents,
                bid_count=lot.bid_count,
                closes_at=lot.closes_at,
            )
        )

    def close(self, closing: LotClosing, recorded_at: datetime) -> bool:
        row = self._session.get_one(LotRow, closing.lot_id)
        if row.status == LotStatus.CLOSED.value:
            return False
        row.status = LotStatus.CLOSED.value
        self._session.add(
            LotClosingRow(
                lot_id=closing.lot_id,
                closed_at=closing.closed_at,
                final_bid_cents=closing.final_bid.cents,
                bid_count=closing.bid_count,
                title=closing.title,
                category=closing.category,
                recorded_at=recorded_at,
            )
        )
        self._session.flush()
        return True

    def open_lots(self, source: str) -> list[StoredLot]:
        rows = self._session.scalars(
            select(LotRow)
            .where(LotRow.source == source, LotRow.status == LotStatus.OPEN.value)
            .order_by(LotRow.closes_at)
        )
        return [to_stored_lot(row) for row in rows]

    def _apply(self, row: LotRow, lot: ScrapedLot, seen_at: datetime) -> None:
        row.title = lot.title
        row.category = lot.category
        row.auction_id = lot.auction_id
        row.current_bid_cents = lot.current_bid.cents
        row.bid_count = lot.bid_count
        row.closes_at = lot.closes_at
        row.url = lot.url
        row.pickup_location = lot.pickup_location
        row.last_scraped_at = seen_at
        if tuple(photo.url for photo in row.photos) != lot.photos:
            if row.photos:
                row.photos.clear()
                self._session.flush()  # delete old rows before reusing their positions
            row.photos.extend(LotPhotoRow(position=i, url=url) for i, url in enumerate(lot.photos))


class SqlScrapeRunLog:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(self, source: str, kind: str, started_at: datetime) -> int:
        row = ScrapeRunRow(
            source=source,
            kind=kind,
            started_at=started_at,
            lots_seen=0,
            lots_new=0,
            lots_changed=0,
            lots_closed=0,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def finish(
        self,
        run_id: int,
        finished_at: datetime,
        *,
        lots_seen: int,
        lots_new: int,
        lots_changed: int,
        lots_closed: int,
        error: str | None = None,
    ) -> None:
        row = self._session.get_one(ScrapeRunRow, run_id)
        row.finished_at = finished_at
        row.lots_seen = lots_seen
        row.lots_new = lots_new
        row.lots_changed = lots_changed
        row.lots_closed = lots_closed
        row.error = error

    def latest(self, source: str, kind: str | None = None) -> ScrapeRun | None:
        query = select(ScrapeRunRow).where(ScrapeRunRow.source == source)
        if kind is not None:
            query = query.where(ScrapeRunRow.kind == kind)
        row = self._session.scalars(query.order_by(ScrapeRunRow.started_at.desc()).limit(1)).first()
        if row is None:
            return None
        return ScrapeRun(
            id=row.id,
            source=row.source,
            kind=row.kind,
            started_at=row.started_at,
            finished_at=row.finished_at,
            lots_seen=row.lots_seen,
            lots_new=row.lots_new,
            lots_changed=row.lots_changed,
            lots_closed=row.lots_closed,
            error=row.error,
        )


class SqlSettingsStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> Any | None:
        row = self._session.get(SettingRow, key)
        return None if row is None else row.value

    def put(self, key: str, value: Any, updated_at: datetime) -> None:
        row = self._session.get(SettingRow, key)
        if row is None:
            self._session.add(SettingRow(key=key, value=value, updated_at=updated_at))
        else:
            row.value = value
            row.updated_at = updated_at


class SqlUnitOfWork:
    lots: SqlLotStore
    runs: SqlScrapeRunLog
    settings: SqlSettingsStore

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.lots = SqlLotStore(self._session)
        self.runs = SqlScrapeRunLog(self._session)
        self.settings = SqlSettingsStore(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._session.rollback()
        self._session.close()

    def commit(self) -> None:
        self._session.commit()
