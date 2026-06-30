"""consolidate_current_schema — no-op head migration for PostgreSQL

This migration is intentionally empty. The actual schema is already
fully defined by the two previous migrations:

  f3ddf3a4f48e (initial_schema)
  ac5e70cab29c (group_olympiads_add_profiles_table)

On a fresh PostgreSQL database, `alembic upgrade head` applies both
of those migrations in order, resulting in the correct final schema.

On existing SQLite databases, this migration is a no-op — the schema
is already at the correct state.

Revision ID: b7c8d9e0f1a2
Revises: ac5e70cab29c
Create Date: 2026-06-30
"""

from collections.abc import Sequence

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "ac5e70cab29c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op — schema is already current."""
    pass


def downgrade() -> None:
    """No-op — nothing to roll back."""
    pass
