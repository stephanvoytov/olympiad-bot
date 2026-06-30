"""
Telegram Bot — точка входа.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import APP_URL, BOT_TOKEN, USE_WEBHOOK, WEBHOOK_SECRET, WEBHOOK_URL

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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
    if is_https:
        builder.row(
            InlineKeyboardButton(text="Панель управления", web_app=WebAppInfo(url=f"{APP_URL}/"))
        )
    return builder.as_markup()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"User @{message.from_user.username} ({message.from_user.id}): /start")
    keyboard = tg_keyboard()
    text = (
        f"{message.from_user.first_name}, добро пожаловать.\n\n"
        "Бот отслеживает олимпиады: напоминает о регистрациях, этапах и дедлайнах.\n\n"
        f"Панель управления: {APP_URL}/\n\n"
        "Откройте в браузере, чтобы добавить олимпиады и настроить статусы."
    )
    try:
        await message.answer(text, reply_markup=keyboard)
        logger.info(f"Response sent to {message.from_user.id}")
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
    try:
        await message.answer(
            f"Панель управления: {APP_URL}/\n\n"
            "Добавляйте олимпиады, следите за этапами и статусами."
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
