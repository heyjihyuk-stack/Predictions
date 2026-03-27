"""Tests for the new API routes."""


def test_market_overview(client):
    response = client.get("/api/markets/overview")
    assert response.status_code == 200
    data = response.get_json()
    assert "available_indices" in data
    assert "available_forex" in data
    assert "sp500" in data["available_indices"]
    assert "usd_krw" in data["available_forex"]


def test_unknown_index_returns_404(client):
    response = client.get("/api/markets/indices/nonexistent")
    assert response.status_code == 404


def test_unknown_forex_returns_404(client):
    response = client.get("/api/markets/forex/nonexistent")
    assert response.status_code == 404


def test_prediction_changes_empty(client):
    response = client.get("/api/predictions/changes")
    assert response.status_code == 200
    data = response.get_json()
    assert "changes" in data


def test_index_page_serves(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Predictions" in response.data
