"""
Сервис напоминаний — проверяет этапы олимпиад и отправляет уведомления.
Запускается как отдельная задача (периодическая проверка).
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot

from bot.config import BOT_TOKEN
from database.db import SessionLocal
from database.models import Stage, User, UserOlympiad

logger = logging.getLogger(__name__)

# Один Bot на весь модуль
_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=BOT_TOKEN)
    return _bot


async def send_telegram_message(telegram_id: int, text: str):
    """Отправить сообщение пользователю через Bot API"""
    bot = get_bot()
    try:
        await bot.send_message(chat_id=telegram_id, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")


async def check_and_notify():
    """
    Проверить все этапы и отправить напоминания.
    """
    db = SessionLocal()
    try:
        now = datetime.now(UTC)

        # Берём все неотправленные этапы на ближайшие 30 дней
        window_end = now + timedelta(days=30)

        stages_to_notify = (
            db.query(Stage, UserOlympiad, User)
            .join(UserOlympiad, Stage.user_olympiad_id == UserOlympiad.id)
            .join(User, UserOlympiad.user_id == User.id)
            .filter(
                Stage.is_completed == False,  # noqa: E712
                Stage.notified == False,  # noqa: E712
                User.notify_enabled == True,  # noqa: E712
                (
                    (Stage.date_end.isnot(None) & Stage.date_end.between(now, window_end))
                    | (Stage.date_start.isnot(None) & Stage.date_start.between(now, window_end))
                ),
            )
            .all()
        )

        for stage, uo, user in stages_to_notify:
            # Выбираем целевую дату (date_end приоритетнее)
            target_date = stage.date_end or stage.date_start
            days_left = (target_date - now).days + 1

            # Учитываем персональную настройку notify_days_before
            if days_left > user.notify_days_before:
                continue

            olympiad_name = uo.olympiad_ref.name

            text = (
                f"Напоминание\n\n"
                f"Олимпиада: {olympiad_name}\n"
                f"Этап: {stage.name}\n"
                f"Дата: {target_date.strftime('%d.%m.%Y')}\n"
                f"Осталось дней: {days_left}"
            )

            await send_telegram_message(user.telegram_id, text)
            stage.notified = True
            logger.info(
                f"Notification sent to {user.telegram_id} for {olympiad_name}: {stage.name}"
            )

        db.commit()

    except Exception as e:
        logger.error(f"Notifier error: {e}")
    finally:
        db.close()


async def notifier_loop(interval_minutes: int = 60):
    """Запускать проверку каждые interval_minutes минут"""
    logger.info(f"Notifier started, checking every {interval_minutes} min")
    while True:
        await check_and_notify()
        await asyncio.sleep(interval_minutes * 60)
