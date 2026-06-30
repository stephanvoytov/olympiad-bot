"""add_indexes — performance indexes for PostgreSQL

Adds indexes on frequently queried columns to avoid sequential scans
as the database grows.

Revision ID: d4e5f6a7b8c9
Revises: b7c8d9e0f1a2
Create Date: 2026-06-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Users
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    # Olympiad profiles
    op.create_index("ix_olympiad_profiles_olympiad_id", "olympiad_profiles", ["olympiad_id"])

    # User olympiads
    op.create_index("ix_user_olympiads_user_id", "user_olympiads", ["user_id"])
    op.create_index("ix_user_olympiads_olympiad_id", "user_olympiads", ["olympiad_id"])
    op.create_index("ix_user_olympiads_user_status", "user_olympiads", ["user_id", "status"])

    # Stages
    op.create_index("ix_stages_user_olympiad_id", "stages", ["user_olympiad_id"])
    op.create_index("ix_stages_dates", "stages", ["date_start", "date_end"])


def downgrade() -> None:
    op.drop_index("ix_stages_dates")
    op.drop_index("ix_stages_user_olympiad_id")
    op.drop_index("ix_user_olympiads_user_status")
    op.drop_index("ix_user_olympiads_olympiad_id")
    op.drop_index("ix_user_olympiads_user_id")
    op.drop_index("ix_olympiad_profiles_olympiad_id")
    op.drop_index("ix_users_telegram_id")
