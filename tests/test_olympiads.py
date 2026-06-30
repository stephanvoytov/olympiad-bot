"""Tests for olympiad catalog API endpoints."""


def test_list_olympiads_empty(client):
    """Catalog returns empty list when no data seeded."""
    resp = client.get("/api/olympiads")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_olympiads_with_data(client, sample_olympiad):
    """Catalog returns seeded olympiads."""
    resp = client.get("/api/olympiads")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "so-math"
    assert len(data[0]["profiles"]) == 1
    assert data[0]["profiles"][0]["slug"] == "math"
    assert data[0]["profiles"][0]["level"] == 1


def test_search_olympiads(client, sample_olympiad):
    """Search by name works."""
    resp = client.get("/api/olympiads?search=Sample")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get("/api/olympiads?search=NonExistent")
    assert resp.status_code == 200
    assert resp.json() == []


def test_filter_by_level(client, sample_olympiad):
    """Filter by profile level works."""
    resp = client.get("/api/olympiads?level=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get("/api/olympiads?level=3")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_olympiad_detail(client, sample_olympiad):
    """Single olympiad detail endpoint."""
    resp = client.get("/api/olympiads/so-math")
    assert resp.status_code == 200
    assert resp.json()["id"] == "so-math"

    resp = client.get("/api/olympiads/nonexistent")
    assert resp.status_code == 404
