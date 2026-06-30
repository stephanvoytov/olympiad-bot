#!/usr/bin/env python
"""
Перенос данных из SQLite в PostgreSQL.

Запускать после применения всех alembic миграций на PG.
Скрипт идемпотентен — при повторном запуске не дублирует данные.

Использование:
  export DATABASE_URL=postgresql://olympiad:pass@localhost:5432/olympiadb
  python scripts/migrate_sqlite_to_pg.py --sqlite ./olympiad_bot.db
"""

import argparse
import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument(
        "--sqlite",
        default="./olympiad_bot.db",
        help="Path to SQLite database file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    pg_url = __import__("os").getenv("DATABASE_URL", "")
    if not pg_url or "postgresql" not in pg_url:
        logger.error("Set DATABASE_URL to your PostgreSQL connection string")
        sys.exit(1)

    from sqlalchemy import create_engine, text

    sqlite_engine = create_engine(f"sqlite:///{args.sqlite}")
    pg_engine = create_engine(pg_url)

    # Проверяем, есть ли что переносить
    with sqlite_engine.connect() as conn:
        user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        olympiad_count = conn.execute(text("SELECT COUNT(*) FROM olympiads")).scalar()
        profile_count = conn.execute(text("SELECT COUNT(*) FROM olympiad_profiles")).scalar()
        uo_count = conn.execute(text("SELECT COUNT(*) FROM user_olympiads")).scalar()
        stage_count = conn.execute(text("SELECT COUNT(*) FROM stages")).scalar()

    logger.info(
        "SQLite data found: %d users, %d olympiads, %d profiles, %d user_olympiads, %d stages",
        user_count,
        olympiad_count,
        profile_count,
        uo_count,
        stage_count,
    )

    if user_count == 0 and olympiad_count == 0:
        logger.info("No data to migrate")
        return

    # Переносим данные через сырой SQL для скорости
    with sqlite_engine.connect() as src:
        with pg_engine.begin() as dst:
            # Проверяем, не переносили ли уже
            existing = dst.execute(text("SELECT COUNT(*) FROM users")).scalar()
            if existing > 0:
                logger.warning("PostgreSQL already has %d users — skipping migration", existing)
                return

            # 1. Olympiads (справочник)
            rows = src.execute(
                text("SELECT id, name, organizer, url, registration_url, tags FROM olympiads")
            ).fetchall()
            for row in rows:
                dst.execute(
                    text(
                        "INSERT INTO olympiads (id, name, organizer, url, registration_url, tags) "
                        "VALUES (:id, :name, :organizer, :url, :registration_url, :tags) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": row[0],
                        "name": row[1],
                        "organizer": row[2],
                        "url": row[3],
                        "registration_url": row[4],
                        "tags": row[5] or "[]",
                    },
                )
            logger.info("Migrated %d olympiads", len(rows))

            # 2. OlympiadProfiles
            rows = src.execute(
                text(
                    "SELECT id, olympiad_id, slug, name, level, benefits, typical_stages "
                    "FROM olympiad_profiles"
                )
            ).fetchall()
            for row in rows:
                dst.execute(
                    text(
                        "INSERT INTO olympiad_profiles "
                        "(id, olympiad_id, slug, name, level, benefits, typical_stages) "
                        "VALUES (:id, :olympiad_id, :slug, :name, :level, "
                        ":benefits, :typical_stages) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": row[0],
                        "olympiad_id": row[1],
                        "slug": row[2],
                        "name": row[3],
                        "level": row[4],
                        "benefits": row[5] or "{}",
                        "typical_stages": row[6] or "[]",
                    },
                )
            logger.info("Migrated %d olympiad_profiles", len(rows))

            # 3. Users
            rows = src.execute(
                text(
                    "SELECT id, telegram_id, username, full_name, created_at, "
                    "notify_enabled, notify_days_before FROM users"
                )
            ).fetchall()
            for row in rows:
                created_at = row[4]
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                dst.execute(
                    text(
                        "INSERT INTO users (id, telegram_id, username, full_name, created_at, "
                        "notify_enabled, notify_days_before) "
                        "VALUES (:id, :telegram_id, :username, :full_name, :created_at, "
                        ":notify_enabled, :notify_days_before) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": row[0],
                        "telegram_id": row[1],
                        "username": row[2],
                        "full_name": row[3],
                        "created_at": created_at,
                        "notify_enabled": row[5],
                        "notify_days_before": row[6],
                    },
                )
            logger.info("Migrated %d users", len(rows))

            # 4. UserOlympiads
            rows = src.execute(
                text(
                    "SELECT id, user_id, olympiad_id, profile_slug, "
                    "status, priority, notes, created_at "
                    "FROM user_olympiads"
                )
            ).fetchall()
            for row in rows:
                created_at = row[7]
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                dst.execute(
                    text(
                        "INSERT INTO user_olympiads (id, user_id, olympiad_id, profile_slug, "
                        "status, priority, notes, created_at) "
                        "VALUES (:id, :user_id, :olympiad_id, :profile_slug, "
                        ":status, :priority, :notes, :created_at) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": row[0],
                        "user_id": row[1],
                        "olympiad_id": row[2],
                        "profile_slug": row[3],
                        "status": row[4],
                        "priority": row[5],
                        "notes": row[6],
                        "created_at": created_at,
                    },
                )
            logger.info("Migrated %d user_olympiads", len(rows))

            # 5. Stages
            rows = src.execute(
                text(
                    "SELECT id, user_olympiad_id, name, date_start, date_end, "
                    "is_completed, result, notified FROM stages"
                )
            ).fetchall()
            for row in rows:
                date_start = row[3]
                date_end = row[4]
                if isinstance(date_start, str):
                    date_start = datetime.fromisoformat(date_start) if date_start else None
                if isinstance(date_end, str):
                    date_end = datetime.fromisoformat(date_end) if date_end else None
                dst.execute(
                    text(
                        "INSERT INTO stages (id, user_olympiad_id, name, date_start, date_end, "
                        "is_completed, result, notified) "
                        "VALUES (:id, :user_olympiad_id, :name, :date_start, :date_end, "
                        ":is_completed, :result, :notified) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": row[0],
                        "user_olympiad_id": row[1],
                        "name": row[2],
                        "date_start": date_start,
                        "date_end": date_end,
                        "is_completed": row[5],
                        "result": row[6],
                        "notified": row[7],
                    },
                )
            logger.info("Migrated %d stages", len(rows))

            # Сброс последовательностей для PG
            dst.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM users), 1))"
                )
            )
            dst.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('olympiad_profiles', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM olympiad_profiles), 1))"
                )
            )
            dst.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('user_olympiads', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM user_olympiads), 1))"
                )
            )
            dst.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('stages', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM stages), 1))"
                )
            )

    logger.info("Migration complete!")


if __name__ == "__main__":
    main()
