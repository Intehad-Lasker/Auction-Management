"""create settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import rosehill.storage.db

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", rosehill.storage.db.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("settings")
