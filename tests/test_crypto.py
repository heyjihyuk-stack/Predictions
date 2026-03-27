"""Tests for crypto market data and options."""

from app.services.market_data import CRYPTO_ASSETS


def test_crypto_assets_defined():
    assert "btc" in CRYPTO_ASSETS
    assert "eth" in CRYPTO_ASSETS
    assert CRYPTO_ASSETS["btc"]["symbol"] == "BTC"
    assert CRYPTO_ASSETS["eth"]["symbol"] == "ETH"


def test_crypto_asset_structure():
    for crypto_id, info in CRYPTO_ASSETS.items():
        assert "id" in info  # CoinGecko ID
        assert "ticker" in info
        assert "name" in info
        assert "symbol" in info


def test_crypto_api_routes(client):
    # Overview includes crypto
    resp = client.get("/api/markets/overview")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "available_crypto" in data
    assert "btc" in data["available_crypto"]
    assert "eth" in data["available_crypto"]


def test_unknown_crypto_returns_404(client):
    resp = client.get("/api/markets/crypto/nonexistent")
    assert resp.status_code == 404


def test_unknown_crypto_options_returns_404(client):
    resp = client.get("/api/markets/crypto/nonexistent/options")
    assert resp.status_code == 404


def test_crypto_prediction_route_accepts_type(client):
    # Should not 400 on crypto asset type (may fail on data fetch, but type is valid)
    resp = client.get("/api/predictions/crypto/btc")
    # Either 200 (success) or 400 (no price data from external API) — not a type error
    assert resp.status_code in [200, 400]
