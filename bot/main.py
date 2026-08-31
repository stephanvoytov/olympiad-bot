"""
Telegram Bot — точка входа.
"""

import asyncio
import logging
import secrets

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import APP_URL, BOT_TOKEN, USE_WEBHOOK, WEBHOOK_SECRET, WEBHOOK_URL
from database.db import SessionLocal
from database.models import User

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def generate_site_password() -> str:
    """6-значный числовой пароль — простой, легко ввести."""
    return str(secrets.randbelow(900000) + 100000)


def get_or_create_user(telegram_id: int, username: str | None = None, full_name: str | None = None) -> tuple:
    """Получить или создать пользователя. Возвращает (user, password)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            pwd = generate_site_password()
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                site_password=pwd,
            )
            db.add(user)
            db.commit()
            return user, pwd
        if not user.site_password:
            pwd = generate_site_password()
            user.site_password = pwd
            db.commit()
            return user, pwd
        return user, user.site_password
    finally:
        db.close()


def tg_keyboard():
    """
    Создать клавиатуру.
    Telegram НЕ ПРИНИМАЕТ HTTP URL в кнопках — ни WebApp, ни обычные.
    При HTTP возвращаем None (только текст).
    """
    is_https = APP_URL.startswith("https")
    if not is_https:
        return None  # без кнопок — Telegram блокирует HTTP

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Панель управления", web_app=WebAppInfo(url=f"{APP_URL}/"))
    )
    return builder.as_markup()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"User @{message.from_user.username} ({user_id}): /start")

    user, site_password = get_or_create_user(
        telegram_id=user_id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
    )

    keyboard = tg_keyboard()
    text = (
        f"👋 {message.from_user.first_name}, добро пожаловать!\n\n"
        "Бот отслеживает олимпиады: напоминает о регистрациях, этапах и дедлайнах.\n\n"
        f"🔐 Данные для входа на сайт:\n"
        f"   ID: {user_id}\n"
        f"   Пароль: {site_password}\n\n"
        f"Откройте {APP_URL}/ и войдите по ID + пароль.\n\n"
        "Панель управления:"
    )
    try:
        await message.answer(text, reply_markup=keyboard)
        logger.info(f"Response sent to {user_id}")
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        try:
            await message.answer(text)
        except Exception as e2:
            logger.error(f"Failed without buttons: {e2}")


@dp.message()
async def fallback(message: types.Message):
    """Любое сообщение — отправляем ссылку на панель"""
    logger.info(f"Message from {message.from_user.id}: {message.text}")
    user, site_password = get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
    )
    try:
        await message.answer(
            f"Панель управления: {APP_URL}/\n\n"
            f"Ваш ID: {user.telegram_id}\n"
            f"Пароль для сайта: {site_password}\n\n"
            "Войдите на сайте по ID + пароль."
        )
        logger.info(f"Fallback response sent to {message.from_user.id}")
    except Exception as e:
        logger.error(f"Fallback error: {e}")


async def on_startup():
    logger.info("Database initialized (migrations handled by entrypoint)")

    if USE_WEBHOOK:
        await bot.set_webhook(
            url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET, drop_pending_updates=True
        )
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Polling mode")


async def on_shutdown():
    if USE_WEBHOOK:
        await bot.delete_webhook()
    await bot.session.close()
    logger.info("Bot stopped")


async def main():
    await on_startup()
    try:
        if USE_WEBHOOK:
            import uvicorn

            from web.main import app as fastapi_app

            logger.info("Starting FastAPI + Bot (webhook mode)")
            config = uvicorn.Config(
                fastapi_app, host="0.0.0.0", port=8000, log_level="info", log_config=None
            )
            server = uvicorn.Server(config)
            await server.serve()
        else:
            logger.info("Starting Bot (polling mode)")
            await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
