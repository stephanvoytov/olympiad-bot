"""
FastAPI приложение — API для Mini App.
"""

import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from bot.config import BOT_TOKEN
from database.db import get_db
from database.models import Olympiad, OlympiadProfile, Stage, User, UserOlympiad

logger = logging.getLogger(__name__)

# ─────────────────────────────── APP SETUP ───────────────────────────────

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "https://olympiad.info.gf").split(",")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Lifespan: seed data on startup, cleanup on shutdown."""
    _seed_olympiads()
    yield


app = FastAPI(
    title="Olympiad Bot API",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["X-Telegram-Init-Data", "Content-Type"],
)

# Rate limiter: 60 запросов/мин с одного IP
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─────────────────────────────── PYDANTIC MODELS ───────────────────────────────


class AddOlympiadRequest(BaseModel):
    olympiad_id: str
    profile_slug: str


class AddStageRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    date_start: str | None = None
    date_end: str | None = None


class UpdateStatusRequest(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(planned|registered|participating|passed_round|won)$",
    )


class DeleteOlympiadRequest(BaseModel):
    telegram_id: int | None = None


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    full_name: str | None = None
    notify_enabled: bool = True
    notify_days_before: int = 3


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


# ─────────────────────────────── AUTH ───────────────────────────────


def verify_telegram_init_data(init_data: str) -> dict | None:
    """Проверить initData из Telegram WebApp."""
    try:
        parsed = parse_qs(init_data)
        data = {k: v[0] for k, v in parsed.items()}
        hash_received = data.pop("hash", None)
        if not hash_received:
            return None
        sorted_keys = sorted(data.keys())
        data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted_keys)
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if computed_hash != hash_received:
            return None
        auth_date = int(data.get("auth_date", 0))
        if datetime.now().timestamp() - auth_date > 86400:
            logger.warning("InitData auth_date expired")
            return None
        return data
    except Exception as e:
        logger.error(f"InitData verification failed: {e}")
        return None


def get_telegram_user_from_init_data(request: Request) -> dict:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data")
    verified = verify_telegram_init_data(init_data)
    if not verified:
        raise HTTPException(status_code=401, detail="Invalid init data")
    try:
        user_str = verified.get("user", "{}")
        return json.loads(user_str)
    except (json.JSONDecodeError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid user data")


def _get_telegram_id(request: Request) -> int:
    """Получить telegram_id из initData."""
    tg_info = get_telegram_user_from_init_data(request)
    tid = tg_info.get("id")
    if not tid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return tid


# ─────────────────────────────── HELPERS ───────────────────────────────


def _serialize_profile(p: OlympiadProfile) -> dict:
    return {
        "slug": p.slug,
        "name": p.name,
        "level": p.level,
        "benefits": p.benefits or {},
        "stages": p.typical_stages or [],
    }


def _serialize_olympiad(o: Olympiad) -> dict:
    return {
        "id": o.id,
        "name": o.name,
        "organizer": o.organizer,
        "url": o.url,
        "registration_url": o.registration_url or o.url,
        "tags": o.tags or [],
        "profiles": [_serialize_profile(p) for p in o.olympiad_profiles],
    }


def _get_profile(olympiad_id: str, profile_slug: str, db: Session) -> OlympiadProfile | None:
    return (
        db.query(OlympiadProfile)
        .filter(
            OlympiadProfile.olympiad_id == olympiad_id,
            OlympiadProfile.slug == profile_slug,
        )
        .first()
    )


# ─────────────────────────────── HEALTH ───────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health():
    """Healthcheck с проверкой подключения к БД."""
    db_status = "unknown"
    try:
        from sqlalchemy import text

        from database.db import SessionLocal

        s = SessionLocal()
        s.execute(text("SELECT 1"))
        s.close()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
        logger.error(f"Health DB check failed: {e}")

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        version="1.1.0",
    )


# ─────────────────────────────── PAGES ───────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def mini_app_index():
    with open("static/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ─────────────────────────────── USER ───────────────────────────────


@app.get("/api/user/me", response_model=UserResponse)
async def get_user(
    request: Request,
    db: Session = Depends(get_db),
):
    tg_info = get_telegram_user_from_init_data(request)
    telegram_id = tg_info.get("id")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=tg_info.get("username"),
            full_name=f"{tg_info.get('first_name', '')} {tg_info.get('last_name', '')}".strip(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        full_name=user.full_name,
        notify_enabled=user.notify_enabled,
        notify_days_before=user.notify_days_before,
    )


# ─────────────────────────────── CATALOG ───────────────────────────────


@app.get("/api/olympiads")
async def list_olympiads(
    search: str | None = Query(None),
    profile: str | None = Query(None),
    level: int | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Olympiad)
    if search:
        query = query.filter(
            Olympiad.name.ilike(f"%{search}%") | Olympiad.organizer.ilike(f"%{search}%")
        )
    olympiads = query.all()
    result = []
    for o in olympiads:
        profiles = o.olympiad_profiles
        if profile:
            profiles = [
                p
                for p in profiles
                if profile.lower() in p.name.lower() or profile.lower() in p.slug.lower()
            ]
        if level:
            profiles = [p for p in profiles if p.level == level]
        if profiles:
            result.append(
                {
                    "id": o.id,
                    "name": o.name,
                    "organizer": o.organizer,
                    "url": o.url,
                    "registration_url": o.registration_url or o.url,
                    "tags": o.tags or [],
                    "profiles": [_serialize_profile(p) for p in profiles],
                }
            )
    return result


@app.get("/api/olympiads/{olympiad_id}")
async def get_olympiad_detail(olympiad_id: str, db: Session = Depends(get_db)):
    o = db.query(Olympiad).filter(Olympiad.id == olympiad_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Olympiad not found")
    return _serialize_olympiad(o)


# ─────────────────────────────── MY OLYMPIADS ───────────────────────────────


@app.get("/api/my-olympiads")
async def list_my_olympiads(
    request: Request,
    telegram_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    tid = telegram_id
    if not tid:
        try:
            tid = _get_telegram_id(request)
        except HTTPException:
            raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.telegram_id == tid).first()
    if not user:
        return []

    result = []
    for uo in user.olympiads:
        olympiad = uo.olympiad_ref
        stages_data = [
            {
                "id": s.id,
                "name": s.name,
                "date_start": s.date_start.isoformat() if s.date_start else None,
                "date_end": s.date_end.isoformat() if s.date_end else None,
                "is_completed": s.is_completed,
                "result": s.result,
            }
            for s in uo.stages
        ]
        profile = _get_profile(olympiad.id, uo.profile_slug, db) if uo.profile_slug else None
        obj = {
            "id": uo.id,
            "olympiad_id": olympiad.id,
            "name": olympiad.name,
            "organizer": olympiad.organizer,
            "url": olympiad.url,
            "registration_url": olympiad.registration_url or olympiad.url,
            "status": uo.status,
            "priority": uo.priority,
            "notes": uo.notes,
            "stages": stages_data,
        }
        if profile:
            obj["profile_slug"] = profile.slug
            obj["profile_name"] = profile.name
            obj["level"] = profile.level
            obj["benefits"] = profile.benefits or {}
        else:
            obj["profile_slug"] = None
            obj["profile_name"] = None
            obj["level"] = None
            obj["benefits"] = {}
        result.append(obj)
    return result


@app.post("/api/my-olympiads/add")
@limiter.limit("20/minute")
async def add_olympiad(
    body: AddOlympiadRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    telegram_id = _get_telegram_id(request)
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    olympiad = db.query(Olympiad).filter(Olympiad.id == body.olympiad_id).first()
    if not olympiad:
        raise HTTPException(status_code=404, detail="Olympiad not found")

    profile = _get_profile(body.olympiad_id, body.profile_slug, db)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile_slug}' not found")

    existing = (
        db.query(UserOlympiad)
        .filter(
            UserOlympiad.user_id == user.id,
            UserOlympiad.olympiad_id == body.olympiad_id,
            UserOlympiad.profile_slug == body.profile_slug,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Profile already added")

    uo = UserOlympiad(
        user_id=user.id,
        olympiad_id=body.olympiad_id,
        profile_slug=body.profile_slug,
        status="planned",
    )
    db.add(uo)
    db.flush()

    for stage_tpl in profile.typical_stages:
        date_start = None
        date_end = None
        if stage_tpl.get("date_start"):
            try:
                date_start = datetime.fromisoformat(stage_tpl["date_start"])
            except (ValueError, TypeError):
                pass
        if stage_tpl.get("date_end"):
            try:
                date_end = datetime.fromisoformat(stage_tpl["date_end"])
            except (ValueError, TypeError):
                pass
        stage = Stage(
            user_olympiad_id=uo.id,
            name=stage_tpl["name"],
            date_start=date_start,
            date_end=date_end,
        )
        db.add(stage)

    db.commit()
    db.refresh(uo)
    return {
        "id": uo.id,
        "olympiad_id": body.olympiad_id,
        "profile_slug": body.profile_slug,
        "status": "added",
    }


@app.post("/api/my-olympiads/{entry_id}/stage")
@limiter.limit("30/minute")
async def add_stage(
    entry_id: int,
    body: AddStageRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    telegram_id = _get_telegram_id(request)
    uo = db.query(UserOlympiad).filter(UserOlympiad.id == entry_id).first()
    if not uo:
        raise HTTPException(status_code=404, detail="Entry not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or uo.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    stage = Stage(
        user_olympiad_id=uo.id,
        name=body.name,
        date_start=datetime.fromisoformat(body.date_start) if body.date_start else None,
        date_end=datetime.fromisoformat(body.date_end) if body.date_end else None,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return {"id": stage.id, "status": "created"}


@app.post("/api/my-olympiads/{entry_id}/status")
async def update_status(
    entry_id: int,
    body: UpdateStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    telegram_id = _get_telegram_id(request)
    uo = db.query(UserOlympiad).filter(UserOlympiad.id == entry_id).first()
    if not uo:
        raise HTTPException(status_code=404, detail="Entry not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or uo.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    uo.status = body.status
    db.commit()
    return {"status": body.status}


@app.delete("/api/my-olympiads/{entry_id}")
async def delete_olympiad(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    telegram_id = _get_telegram_id(request)
    uo = db.query(UserOlympiad).filter(UserOlympiad.id == entry_id).first()
    if not uo:
        raise HTTPException(status_code=404, detail="Entry not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or uo.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db.delete(uo)
    db.commit()
    return {"status": "deleted"}


# ─────────────────────────────── DASHBOARD ───────────────────────────────


@app.get("/api/dashboard")
async def dashboard(
    request: Request,
    telegram_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    tid = telegram_id if telegram_id else None
    if not tid:
        try:
            tid = _get_telegram_id(request)
        except HTTPException:
            return {"total": 0, "by_status": {}, "upcoming_events": []}

    user = db.query(User).filter(User.telegram_id == tid).first()
    if not user:
        return {"total": 0, "by_status": {}, "upcoming_events": []}

    total = len(user.olympiads)
    by_status: dict[str, int] = {}
    upcoming = []
    for uo in user.olympiads:
        by_status[uo.status] = by_status.get(uo.status, 0) + 1
        for stage in uo.stages:
            if stage.is_completed:
                continue
            target_date = stage.date_start or stage.date_end
            if target_date:
                upcoming.append(
                    {
                        "olympiad_name": uo.olympiad_ref.name,
                        "stage_name": stage.name,
                        "date": target_date.isoformat(),
                        "stage_id": stage.id,
                    }
                )
    upcoming.sort(key=lambda x: x["date"])
    return {"total": total, "by_status": by_status, "upcoming_events": upcoming[:10]}


# ─────────────────────────────── SEED ───────────────────────────────


def _seed_olympiads():
    from database.db import SessionLocal

    db = SessionLocal()
    try:
        if db.query(Olympiad).count() > 0:
            return
        with open("data/olympiads.json", encoding="utf-8") as f:
            olympiads_data = json.load(f)
        total_profiles = 0
        for data in olympiads_data:
            olympiad = Olympiad(
                id=data["id"],
                name=data["name"],
                organizer=data.get("organizer"),
                url=data.get("url"),
                registration_url=data.get("registration_url"),
                tags=data.get("tags", []),
            )
            db.add(olympiad)
            db.flush()
            for prof in data.get("profiles", []):
                profile = OlympiadProfile(
                    olympiad_id=olympiad.id,
                    slug=prof["slug"],
                    name=prof["name"],
                    level=prof.get("level"),
                    benefits=prof.get("benefits", {}),
                    typical_stages=prof.get("stages", []),
                )
                db.add(profile)
                total_profiles += 1
        db.commit()
        logger.info(f"Seeded {len(olympiads_data)} olympiads, {total_profiles} profiles")
    except Exception as e:
        logger.error(f"Seed error: {e}")
    finally:
        db.close()
