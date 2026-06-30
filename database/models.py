from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(128), nullable=True)
    full_name = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    notify_enabled = Column(Boolean, default=True)
    notify_days_before = Column(Integer, default=3)

    olympiads = relationship("UserOlympiad", back_populates="user", cascade="all, delete-orphan")


class Olympiad(Base):
    """Справочник: известные олимпиады (загружается из olympiads.json)"""

    __tablename__ = "olympiads"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    organizer = Column(String(256), nullable=True)
    url = Column(Text, nullable=True)
    registration_url = Column(Text, nullable=True)
    tags = Column(JSON, default=list)

    olympiad_profiles = relationship(
        "OlympiadProfile", back_populates="olympiad", cascade="all, delete-orphan"
    )
    user_entries = relationship("UserOlympiad", back_populates="olympiad_ref")


class OlympiadProfile(Base):
    """Профили олимпиады: уровень, льготы, типовые этапы"""

    __tablename__ = "olympiad_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    olympiad_id = Column(String(64), ForeignKey("olympiads.id", ondelete="CASCADE"), nullable=False)
    slug = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    level = Column(Integer, nullable=True)
    benefits = Column(JSON, default=dict)
    typical_stages = Column(JSON, default=list)

    __table_args__ = (UniqueConstraint("olympiad_id", "slug", name="uq_olympiad_profile"),)

    olympiad = relationship("Olympiad", back_populates="olympiad_profiles")


class Stage(Base):
    """Этапы конкретной олимпиады для пользователя"""

    __tablename__ = "stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_olympiad_id = Column(
        Integer, ForeignKey("user_olympiads.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(256), nullable=False)
    date_start = Column(DateTime, nullable=True)
    date_end = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    result = Column(String(64), nullable=True)
    notified = Column(Boolean, default=False)

    user_olympiad = relationship("UserOlympiad", back_populates="stages")


class UserOlympiad(Base):
    """Олимпиады, которые пользователь добавил себе"""

    __tablename__ = "user_olympiads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    olympiad_id = Column(String(64), ForeignKey("olympiads.id"), nullable=False)
    profile_slug = Column(String(64), nullable=True)
    status = Column(String(32), default="planned")
    priority = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    user = relationship("User", back_populates="olympiads")
    olympiad_ref = relationship("Olympiad", back_populates="user_entries")
    stages = relationship(
        "Stage",
        back_populates="user_olympiad",
        cascade="all, delete-orphan",
        order_by="Stage.date_start",
    )
