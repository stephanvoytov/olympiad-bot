"""add_site_password — пароль для входа на сайт без Telegram

Добавляет колонку site_password в таблицу users. Пользователь вводит
свой Telegram ID + пароль (полученный в боте) на сайте, чтобы работать
со своим же профилем вне Telegram.

Revision ID: a1b2c3d4e5f6
Revises: d4e5f6a7b8c9
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("site_password", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "site_password")
