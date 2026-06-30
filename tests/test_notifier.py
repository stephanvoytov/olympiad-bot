"""Tests for notifier logic (notification query)."""

from datetime import UTC, datetime, timedelta

from database.models import Olympiad, Stage, User, UserOlympiad


def _seed_test_data(db_session):
    """Create minimal test data for notifier checks."""
    user = User(
        telegram_id=111,
        username="testuser",
        full_name="Test User",
        notify_enabled=True,
        notify_days_before=3,
    )
    db_session.add(user)
    db_session.flush()

    olympiad = Olympiad(
        id="test-olympiad",
        name="Test Olympiad",
        organizer="Test Org",
    )
    db_session.add(olympiad)
    db_session.flush()

    uo = UserOlympiad(
        user_id=user.id,
        olympiad_id=olympiad.id,
        profile_slug="math",
        status="planned",
    )
    db_session.add(uo)
    db_session.flush()
    return user, olympiad, uo


class TestNotifierQueries:
    """Test the core query that drives notification logic."""

    def test_stage_within_window_finds_upcoming(self, db_session):
        """Stage with date_start within 30 days should be found."""
        user, olympiad, uo = _seed_test_data(db_session)
        now = datetime.now(UTC)
        stage = Stage(
            user_olympiad_id=uo.id,
            name="Отборочный этап",
            date_start=now + timedelta(days=2),
            is_completed=False,
            notified=False,
        )
        db_session.add(stage)
        db_session.commit()

        from database.models import Stage as StageModel

        window_end = now + timedelta(days=30)
        results = (
            db_session.query(StageModel)
            .filter(
                StageModel.is_completed == False,  # noqa: E712
                StageModel.notified == False,  # noqa: E712
                StageModel.date_start.between(now, window_end),
            )
            .all()
        )
        assert len(results) == 1
        assert results[0].name == "Отборочный этап"

    def test_completed_stage_excluded(self, db_session):
        """Completed stages should not trigger notifications."""
        user, olympiad, uo = _seed_test_data(db_session)
        now = datetime.now(UTC)
        stage = Stage(
            user_olympiad_id=uo.id,
            name="Заключительный этап",
            date_start=now + timedelta(days=5),
            is_completed=True,
            notified=False,
        )
        db_session.add(stage)
        db_session.commit()

        from database.models import Stage as StageModel

        window_end = now + timedelta(days=30)
        results = (
            db_session.query(StageModel)
            .filter(
                StageModel.is_completed == False,  # noqa: E712
                StageModel.notified == False,  # noqa: E712
                StageModel.date_start.between(now, window_end),
            )
            .all()
        )
        assert len(results) == 0

    def test_already_notified_excluded(self, db_session):
        """Already notified stages should not be found again."""
        user, olympiad, uo = _seed_test_data(db_session)
        now = datetime.now(UTC)
        stage = Stage(
            user_olympiad_id=uo.id,
            name="Муниципальный этап",
            date_start=now + timedelta(days=3),
            is_completed=False,
            notified=True,
        )
        db_session.add(stage)
        db_session.commit()

        from database.models import Stage as StageModel

        window_end = now + timedelta(days=30)
        results = (
            db_session.query(StageModel)
            .filter(
                StageModel.is_completed == False,  # noqa: E712
                StageModel.notified == False,  # noqa: E712
                StageModel.date_start.between(now, window_end),
            )
            .all()
        )
        assert len(results) == 0

    def test_stage_outside_window_excluded(self, db_session):
        """Stage far in the future should not be found."""
        user, olympiad, uo = _seed_test_data(db_session)
        now = datetime.now(UTC)
        stage = Stage(
            user_olympiad_id=uo.id,
            name="Региональный этап",
            date_start=now + timedelta(days=60),
            is_completed=False,
            notified=False,
        )
        db_session.add(stage)
        db_session.commit()

        from database.models import Stage as StageModel

        window_end = now + timedelta(days=30)
        results = (
            db_session.query(StageModel)
            .filter(
                StageModel.is_completed == False,  # noqa: E712
                StageModel.notified == False,  # noqa: E712
                StageModel.date_start.between(now, window_end),
            )
            .all()
        )
        assert len(results) == 0

    def test_notify_disabled_user_stage_excluded(self, db_session):
        """Stage of a user with notify_enabled=False should not trigger."""
        user, olympiad, uo = _seed_test_data(db_session)
        user.notify_enabled = False
        db_session.flush()

        now = datetime.now(UTC)
        stage = Stage(
            user_olympiad_id=uo.id,
            name="Школьный этап",
            date_start=now + timedelta(days=2),
            is_completed=False,
            notified=False,
        )
        db_session.add(stage)
        db_session.commit()

        # The notifier JOINs User + checks notify_enabled
        from database.models import Stage as StageModel
        from database.models import User as UserModel

        window_end = now + timedelta(days=30)
        results = (
            db_session.query(StageModel)
            .join(UserOlympiad, StageModel.user_olympiad_id == UserOlympiad.id)
            .join(UserModel, UserOlympiad.user_id == UserModel.id)
            .filter(
                StageModel.is_completed == False,  # noqa: E712
                StageModel.notified == False,  # noqa: E712
                UserModel.notify_enabled == True,  # noqa: E712
                StageModel.date_start.between(now, window_end),
            )
            .all()
        )
        assert len(results) == 0
