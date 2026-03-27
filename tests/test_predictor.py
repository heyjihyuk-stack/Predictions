"""Tests for the prediction engine."""

import numpy as np

from app.services.predictor import _technical_analysis, _fallback_forecast


def test_technical_analysis_bullish():
    # Uptrending prices
    prices = [100 + i * 0.5 for i in range(30)]
    result = _technical_analysis(prices)
    assert result["trend"] == "bullish"
    assert result["momentum"] > 0
    assert result["current"] == prices[-1]


def test_technical_analysis_bearish():
    # Downtrending prices
    prices = [100 - i * 0.5 for i in range(30)]
    result = _technical_analysis(prices)
    assert result["trend"] == "bearish"
    assert result["momentum"] < 0


def test_technical_analysis_empty():
    result = _technical_analysis([])
    assert result["trend"] == "neutral"


def test_technical_analysis_short_series():
    result = _technical_analysis([100, 101, 102, 103, 104])
    assert result["trend"] in ["bullish", "bearish", "neutral"]
    assert result["current"] == 104


def test_fallback_forecast():
    technical = {
        "trend": "bullish",
        "momentum": 5.0,
        "volatility": 2.0,
        "current": 5000,
        "support": 4900,
        "resistance": 5100,
        "sma_short": 5050,
        "sma_long": 4980,
    }
    result = _fallback_forecast(technical, "monthly")
    assert "direction" in result
    assert "target_low" in result
    assert "target_mid" in result
    assert "target_high" in result
    assert 0 <= result["confidence"] <= 1
    assert result["target_low"] <= result["target_mid"] <= result["target_high"]
