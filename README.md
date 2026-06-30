# Olympiad Tracker Bot

Telegram bot + Mini App для отслеживания олимпиад, этапов и льгот при поступлении (БВИ, 100 баллов).

## Архитектура

- **Bot** — aiogram 3.x, polling mode
- **API** — FastAPI (Mini App backend)
- **Frontend** — Single HTML/JS/CSS (Telegram WebApp)
- **DB** — PostgreSQL (production) / SQLite (dev)
- **Migrations** — Alembic

## Быстрый старт

```bash
# Клонировать
git clone https://github.com/stephanvoytov/olympiad-bot.git
cd olympiad-bot

# Настроить окружение
cp env.example .env
# Отредактировать .env: BOT_TOKEN, APP_URL

# Запустить
docker compose up -d --build
```

Бот: @olympiadnotifybot  
Mini App: https://olympiad.info.gf

## Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен Telegram бота |
| `APP_URL` | URL Mini App (https://olympiad.info.gf) |
| `USE_WEBHOOK` | false (polling) |
| `DATABASE_URL` | PostgreSQL DSN (опционально — SQLite по умолчанию) |
| `CORS_ORIGINS` | Разрешённые origins для CORS |
| `SENTRY_DSN` | DSN Sentry (опционально) |

## Разработка

```bash
pip install -r requirements.txt
python entrypoint.py          # бот + API
pytest tests/ -v              # тесты
ruff check . && ruff format . # линтинг
```

## Структура

```
├── bot/          # Telegram бот (aiogram)
├── web/          # FastAPI приложение
├── static/       # Frontend (HTML/JS/CSS)
├── database/     # SQLAlchemy модели + engine
├── alembic/      # Миграции
├── scripts/      # Утилиты (бэкап, миграция данных)
├── tests/        # Тесты
└── data/         # Olympiads.json
```
