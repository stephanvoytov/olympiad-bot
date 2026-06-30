"""Tests for /health endpoint."""


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "database" in data
    assert data["version"] == "1.1.0"
