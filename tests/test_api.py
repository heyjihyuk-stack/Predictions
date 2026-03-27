"""Tests for API routes."""


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_sources(client):
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.get_json()
    assert "rss_feeds" in data
