"""Database tables. Money columns hold whole cents; times are UTC.

These classes stay inside `storage/`. Repositories translate them to domain objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from rosehill.storage.db import UTCDateTime


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime}  # noqa: RUF012 (SQLAlchemy API)


class LotRow(Base):
    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("source", "source_id"),
        Index("ix_lots_status_closes_at", "status", "closes_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(120))
    auction_id: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    current_bid_cents: Mapped[int] = mapped_column(Integer)
    bid_count: Mapped[int] = mapped_column(Integer)
    closes_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(16))
    url: Mapped[str] = mapped_column(Text)
    pickup_location: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime]
    last_scraped_at: Mapped[datetime]

    photos: Mapped[list[LotPhotoRow]] = relationship(
        back_populates="lot",
        order_by="LotPhotoRow.position",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LotPhotoRow(Base):
    __tablename__ = "lot_photos"
    __table_args__ = (UniqueConstraint("lot_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)

    lot: Mapped[LotRow] = relationship(back_populates="photos")


class LotSnapshotRow(Base):
    """A lot's bid state each time it changed: the bidding history."""

    __tablename__ = "lot_snapshots"
    __table_args__ = (Index("ix_lot_snapshots_lot_observed", "lot_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"))
    observed_at: Mapped[datetime]
    current_bid_cents: Mapped[int] = mapped_column(Integer)
    bid_count: Mapped[int] = mapped_column(Integer)
    closes_at: Mapped[datetime]


class LotClosingRow(Base):
    """Final price of a closed lot: the price history used by later versions."""

    __tablename__ = "lot_closings"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), unique=True)
    closed_at: Mapped[datetime] = mapped_column(index=True)
    final_bid_cents: Mapped[int] = mapped_column(Integer)
    bid_count: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    recorded_at: Mapped[datetime]


class ScrapeRunRow(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(index=True)
    finished_at: Mapped[datetime | None]
    lots_seen: Mapped[int] = mapped_column(Integer, default=0)
    lots_new: Mapped[int] = mapped_column(Integer, default=0)
    lots_changed: Mapped[int] = mapped_column(Integer, default=0)
    lots_closed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class HttpCacheRow(Base):
    __tablename__ = "http_cache"

    url: Mapped[str] = mapped_column(Text, primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime]


class SettingRow(Base):
    """A business rule edited from the Settings page, such as the fee schedule."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime]
