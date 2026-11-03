"""Alembic environment. Run through `rosehill db upgrade`, which passes in a connection."""

from alembic import context

from rosehill.storage.tables import Base

connection = context.config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    render_as_batch=True,  # SQLite needs table rebuilds for most ALTERs
    compare_type=True,
)
with context.begin_transaction():
    context.run_migrations()
