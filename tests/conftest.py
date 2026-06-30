"""
Pytest fixtures: test database (temporary file), test client, sample data.
"""

import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.db import Base
from database.models import Olympiad, OlympiadProfile

# Temp file for test DB (shared connections work correctly with file-based SQLite)
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
TEST_DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _set_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _get_test_db():
    """FastAPI dependency override for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Get a clean DB session for seeding."""
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def client():
    """FastAPI TestClient with overridden DB dependency."""
    from database.db import get_db
    from web.main import app

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_olympiad(db_session):
    """Create a sample olympiad with profiles for testing."""
    olympiad = Olympiad(
        id="so-math",
        name="Sample Olympiad",
        organizer="Test Org",
        url="https://example.com",
        tags=["math"],
    )
    db_session.add(olympiad)
    db_session.flush()

    profile = OlympiadProfile(
        olympiad_id="so-math",
        slug="math",
        name="Mathematics",
        level=1,
        benefits={"БВИ": "Мехмат МГУ"},
        typical_stages=[
            {"name": "Отборочный этап", "date_start": "2026-10-01"},
            {"name": "Заключительный этап", "date_start": "2026-12-01"},
        ],
    )
    db_session.add(profile)
    db_session.commit()
    return olympiad
