"""
Docker entrypoint — запускает ВСЁ в одном контейнере:
  - FastAPI (Mini App + API)
  - Telegram Bot (polling)
  - Напоминания
"""

import asyncio
import logging
import os
import signal
import sys
import time

import structlog

# ─────────────────────────────── LOGGING ───────────────────────────────

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
        if sys.stderr.isatty()
        else structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = structlog.get_logger("entrypoint")
logger.info("Starting", version="1.1.0")

os.makedirs("/app/data", exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./olympiad_bot.db")

# ─────────────────────────────── SENTRY ───────────────────────────────

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENV", "production"),
        traces_sample_rate=0.1,
    )
    logger.info("Sentry initialized")


# ─────────────────────────────── WAIT-FOR-POSTGRES ───────────────────────────────


def _wait_for_postgres(timeout: int = 30) -> None:
    """Ждём, пока PostgreSQL станет доступен."""
    if not DATABASE_URL.startswith("postgresql"):
        return
    import psycopg2

    logger.info("Waiting for PostgreSQL...")
    start = time.time()
    last_error = None
    while time.time() - start < timeout:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.close()
            logger.info("PostgreSQL is ready")
            return
        except psycopg2.OperationalError as e:
            last_error = e
            time.sleep(1)
    logger.error("PostgreSQL timeout", error=str(last_error))
    sys.exit(1)


# ─────────────────────────────── MIGRATIONS ───────────────────────────────


def run_migrations():
    """Apply Alembic migrations before starting."""
    _wait_for_postgres()
    try:
        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config("/app/alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations up to date")
    except Exception as e:
        logger.warning("Alembic migration failed, falling back to create_all", error=str(e))
        from database.db import init_db

        init_db()


# ─────────────────────────────── GRACEFUL SHUTDOWN ───────────────────────────────


_shutdown_event = asyncio.Event()


def _signal_handler(sig: int, frame) -> None:
    logger.info("Signal received, shutting down...", signal=sig)
    _shutdown_event.set()


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ─────────────────────────────── MAIN ───────────────────────────────


async def main():
    run_migrations()
    import uvicorn

    from bot.main import bot, dp, on_shutdown, on_startup
    from bot.notifier import notifier_loop

    await on_startup()

    from web.main import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        log_config=None,
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    bot_task = asyncio.create_task(dp.start_polling(bot))
    notifier_task = asyncio.create_task(notifier_loop(interval_minutes=60))

    logger.info("All services started: FastAPI + Bot + Notifier")

    # Ждём сигнала завершения
    await _shutdown_event.wait()
    logger.info("Shutting down all services...")

    # Graceful shutdown
    bot_task.cancel()
    notifier_task.cancel()
    server.should_exit = True

    await asyncio.gather(bot_task, notifier_task, server_task, return_exceptions=True)
    await on_shutdown()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error("Fatal error", exc_info=True, error=str(e))
