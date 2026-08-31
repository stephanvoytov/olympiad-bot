"""Add reminded_3d, reminded_1d to stages, drop old notified

Revision ID: e1f2a3b4c5d6
Revises: a1b2c3d4e5f6
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stages", sa.Column("reminded_3d", sa.Boolean(), nullable=True))
    op.add_column("stages", sa.Column("reminded_1d", sa.Boolean(), nullable=True))
    op.drop_column("stages", "notified")


def downgrade() -> None:
    op.add_column("stages", sa.Column("notified", sa.Boolean(), nullable=True))
    op.drop_column("stages", "reminded_1d")
    op.drop_column("stages", "reminded_3d")
