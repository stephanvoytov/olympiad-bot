"""Tests for user olympiad CRUD API endpoints."""

import hashlib
import hmac
from urllib.parse import urlencode

import pytest

from bot.config import BOT_TOKEN


def _make_init_data(user_id: int = 12345) -> str:
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


HEADERS = {"X-Telegram-Init-Data": _make_init_data()}


@pytest.fixture
def created_user(client):
    """Ensure user exists in DB before tests that need it."""
    resp = client.get("/api/user/me", headers=HEADERS)
    assert resp.status_code == 200
    return resp.json()


class TestUserOlympiadCRUD:
    def test_add_olympiad(self, client, sample_olympiad, created_user):
        """Add olympiad returns success."""
        resp = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "added"
        assert data["profile_slug"] == "math"

    def test_add_duplicate_fails(self, client, sample_olympiad, created_user):
        """Adding same profile twice returns 400."""
        client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        resp = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        assert resp.status_code == 400

    def test_add_missing_profile_slug_fails(self, client, sample_olympiad, created_user):
        """Missing profile_slug returns 422 (Pydantic validation)."""
        resp = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math"},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_list_my_olympiads(self, client, sample_olympiad, created_user):
        """List returns added olympiad with profile info."""
        client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        resp = client.get("/api/my-olympiads", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["profile_name"] == "Mathematics"
        assert data[0]["level"] == 1

    def test_list_empty_before_add(self, client):
        """List returns empty before adding anything."""
        resp = client.get("/api/my-olympiads", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_stage(self, client, sample_olympiad, created_user):
        """Adding a stage to a user olympiad works."""
        add = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        assert add.status_code == 200
        entry_id = add.json()["id"]

        resp = client.post(
            f"/api/my-olympiads/{entry_id}/stage",
            json={"name": "Тестовый этап", "date_start": "2026-11-01"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_update_status(self, client, sample_olympiad, created_user):
        """Updating status works."""
        add = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        assert add.status_code == 200
        entry_id = add.json()["id"]

        resp = client.post(
            f"/api/my-olympiads/{entry_id}/status",
            json={"status": "registered"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "registered"

    def test_invalid_status_rejected(self, client, sample_olympiad, created_user):
        """Invalid status value returns 422 (Pydantic regex validation)."""
        add = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        assert add.status_code == 200
        entry_id = add.json()["id"]
        resp = client.post(
            f"/api/my-olympiads/{entry_id}/status",
            json={"status": "invalid_status"},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_delete_olympiad(self, client, sample_olympiad, created_user):
        """Deleting olympiad removes it."""
        add = client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        assert add.status_code == 200
        entry_id = add.json()["id"]

        resp = client.delete(
            f"/api/my-olympiads/{entry_id}",
            headers=HEADERS,
        )
        assert resp.status_code == 200

        # Verify it's gone
        resp = client.get("/api/my-olympiads", headers=HEADERS)
        assert resp.json() == []

    def test_dashboard(self, client, sample_olympiad, created_user):
        """Dashboard returns stats."""
        client.post(
            "/api/my-olympiads/add",
            json={"olympiad_id": "so-math", "profile_slug": "math"},
            headers=HEADERS,
        )
        resp = client.get("/api/dashboard", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["by_status"]["planned"] == 1
