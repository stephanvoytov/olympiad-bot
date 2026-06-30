"""Tests for auth and user endpoints."""

import hashlib
import hmac
from urllib.parse import urlencode

from bot.config import BOT_TOKEN


def _make_init_data(user_id: int = 12345) -> str:
    """Create mock Telegram init data for testing."""
    data = {
        "auth_date": "2000000000",
        "user": f'{{"id":{user_id},"first_name":"Test","username":"testuser"}}',
    }
    sorted_keys = sorted(data.keys())
    data_check_string = "\n".join(f"{k}={data[k]}" for k in sorted_keys)
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    hash_val = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = hash_val
    return urlencode(data)


def test_health_no_auth_needed(client):
    """Health endpoint doesn't require auth."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_user_me_creates_user(client):
    """GET /api/user/me creates user on first call."""
    init_data = _make_init_data(99999)
    resp = client.get("/api/user/me", headers={"X-Telegram-Init-Data": init_data})
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_id"] == 99999
    assert data["username"] == "testuser"


def test_user_me_missing_header(client):
    """Missing init data returns 401."""
    resp = client.get("/api/user/me")
    assert resp.status_code == 401


def test_cors_headers(client):
    """CORS headers are set."""
    resp = client.options(
        "/api/olympiads",
        headers={
            "Origin": "https://olympiad.info.gf",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    # FastAPI TestClient adds CORS on OPTIONS
    cors_origin = resp.headers.get("access-control-allow-origin")
    assert cors_origin == "https://olympiad.info.gf"
