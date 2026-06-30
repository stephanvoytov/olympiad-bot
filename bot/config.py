import os

from dotenv import load_dotenv

# Пробуем загрузить из .env, если нет — из settings.cfg
load_dotenv()
if not os.getenv("BOT_TOKEN"):
    load_dotenv("settings.cfg")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "super-secret")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{APP_URL}{WEBHOOK_PATH}"

# Режим работы: webhook или polling
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
