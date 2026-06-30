"""
Database engine and session management.

Supports PostgreSQL (recommended for production) and SQLite (for local dev).
DATABASE_URL is read from environment; defaults to SQLite for development.
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./olympiad_bot.db",
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        echo=os.getenv("PYTHON_DEBUG", "").lower() in ("1", "true"),
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=os.getenv("PYTHON_DEBUG", "").lower() in ("1", "true"),
    )

# WAL-mode for SQLite
if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Fallback: create all tables directly (not needed when Alembic is used)."""
    Base.metadata.create_all(bind=engine)
