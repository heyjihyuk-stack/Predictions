"""Tests for market data service."""

from app.services.market_data import FOREX_PAIRS, STOCK_INDICES


def test_stock_indices_defined():
    assert len(STOCK_INDICES) >= 9
    assert "sp500" in STOCK_INDICES
    assert "kospi" in STOCK_INDICES
    assert "nikkei" in STOCK_INDICES
    assert "ftse" in STOCK_INDICES
    assert "shanghai" in STOCK_INDICES


def test_forex_pairs_defined():
    assert len(FOREX_PAIRS) >= 5
    assert "usd_krw" in FOREX_PAIRS
    assert "usd_cny" in FOREX_PAIRS
    assert "usd_jpy" in FOREX_PAIRS
    assert "eur_usd" in FOREX_PAIRS
    assert "gbp_usd" in FOREX_PAIRS


def test_index_info_structure():
    for idx_id, info in STOCK_INDICES.items():
        assert "ticker" in info
        assert "name" in info
        assert "country" in info
        assert "currency" in info


def test_forex_info_structure():
    for pair_id, info in FOREX_PAIRS.items():
        assert "ticker" in info
        assert "name" in info
        assert "base" in info
        assert "quote" in info
