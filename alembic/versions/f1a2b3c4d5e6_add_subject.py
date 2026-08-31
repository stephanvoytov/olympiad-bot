"""add subject to olympiad_profiles

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olympiad_profiles", sa.Column("subject", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("olympiad_profiles", "subject")
