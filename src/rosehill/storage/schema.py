"""Applies Alembic migrations from code."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

_MIGRATIONS = Path(__file__).parent / "migrations"


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS))
    return config


def upgrade(engine: Engine, revision: str = "head") -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def make_revision(engine: Engine, message: str) -> None:
    """Autogenerate a migration from the difference between the tables and the database."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.revision(config, message=message, autogenerate=True, rev_id=_next_rev_id())


def _next_rev_id() -> str:
    existing = [p.name for p in (_MIGRATIONS / "versions").glob("[0-9][0-9][0-9][0-9]_*.py")]
    return f"{len(existing) + 1:04d}"
