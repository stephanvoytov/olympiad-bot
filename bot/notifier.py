"""
Сервис напоминаний — проверяет этапы олимпиад и отправляет уведомления.
Отправляет за 3 дня и за 1 день до дедлайна.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot

from bot.config import BOT_TOKEN
from database.db import SessionLocal
from database.models import Olympiad, Stage, User, UserOlympiad

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=BOT_TOKEN)
    return _bot


async def send_telegram_message(telegram_id: int, text: str):
    bot = get_bot()
    try:
        await bot.send_message(chat_id=telegram_id, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")


async def check_and_notify():
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        window_end = now + timedelta(days=7)

        # Берём все незавершённые этапы на ближайшие 7 дней
        stages = (
            db.query(Stage, UserOlympiad, User)
            .join(UserOlympiad, Stage.user_olympiad_id == UserOlympiad.id)
            .join(User, UserOlympiad.user_id == User.id)
            .filter(
                Stage.is_completed == False,  # noqa: E712
                User.notify_enabled == True,  # noqa: E712
                (
                    (Stage.date_end.isnot(None) & Stage.date_end.between(now, window_end))
                    | (Stage.date_start.isnot(None) & Stage.date_start.between(now, window_end))
                ),
            )
            .all()
        )

        sent = 0
        for stage, uo, user in stages:
            target_date = stage.date_end or stage.date_start
            days_left = (target_date - now).days

            # Получаем название олимпиады
            olympiad = db.query(Olympiad).filter(Olympiad.id == uo.olympiad_id).first()
            olympiad_name = olympiad.name if olympiad else "Олимпиада"

            # За 1 день — приоритетнее
            if days_left <= 1 and not stage.reminded_1d:
                text = (
                    f"🔴 ЗАВТРА!\n\n"
                    f"📌 {olympiad_name}\n"
                    f"📅 {stage.name}\n"
                    f"📆 {target_date.strftime('%d.%m.%Y')}"
                )
                await send_telegram_message(user.telegram_id, text)
                stage.reminded_1d = True
                stage.reminded_3d = True  # помечаем и 3д тоже
                sent += 1
                logger.info(f"1d reminder → {user.telegram_id}: {olympiad_name} / {stage.name}")

            # За 3 дня
            elif days_left <= 3 and not stage.reminded_3d:
                text = (
                    f"⏰ Через {days_left} дн.\n\n"
                    f"📌 {olympiad_name}\n"
                    f"📅 {stage.name}\n"
                    f"📆 {target_date.strftime('%d.%m.%Y')}"
                )
                await send_telegram_message(user.telegram_id, text)
                stage.reminded_3d = True
                sent += 1
                logger.info(f"3d reminder → {user.telegram_id}: {olympiad_name} / {stage.name}")

        if sent:
            db.commit()
            logger.info(f"Sent {sent} reminders")

    except Exception as e:
        logger.error(f"Notifier error: {e}")
    finally:
        db.close()


async def notifier_loop(interval_minutes: int = 60):
    logger.info(f"Notifier started, checking every {interval_minutes} min")
    while True:
        await check_and_notify()
        await asyncio.sleep(interval_minutes * 60)
