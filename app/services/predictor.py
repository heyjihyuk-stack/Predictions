"""Prediction engine for market forecasts.

Generates weekly, monthly, quarterly, yearly predictions using:
1. Technical analysis (moving averages, momentum, volatility)
2. LLM-powered analysis incorporating news context
3. Confidence scoring and prediction change tracking
"""

import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from app.services.llm import chat_json
from app.services.market_data import CRYPTO_ASSETS, FOREX_PAIRS, STOCK_INDICES
from config.settings import get_settings

logger = logging.getLogger(__name__)

# Store predictions for change tracking
_prediction_store: dict[str, dict] = {}
PREDICTIONS_FILE = Path("/tmp/predictions_history.json")


def _technical_analysis(prices: list[float]) -> dict:
    """Run basic technical analysis on price data."""
    if not prices or len(prices) < 5:
        return {"trend": "neutral", "momentum": 0, "volatility": 0, "support": None, "resistance": None}

    arr = np.array([p for p in prices if p is not None])
    if len(arr) < 5:
        return {"trend": "neutral", "momentum": 0, "volatility": 0, "support": None, "resistance": None}

    # Trend: compare short MA vs long MA
    short_window = min(5, len(arr))
    long_window = min(20, len(arr))
    short_ma = float(np.mean(arr[-short_window:]))
    long_ma = float(np.mean(arr[-long_window:]))

    if short_ma > long_ma * 1.01:
        trend = "bullish"
    elif short_ma < long_ma * 0.99:
        trend = "bearish"
    else:
        trend = "neutral"

    # Momentum (rate of change)
    momentum = float((arr[-1] - arr[-min(10, len(arr))]) / arr[-min(10, len(arr))]) * 100

    # Volatility (std dev as % of mean)
    volatility = float(np.std(arr[-min(20, len(arr)):]) / np.mean(arr[-min(20, len(arr)):])) * 100

    # Support and resistance (recent lows/highs)
    recent = arr[-min(20, len(arr)):]
    support = float(np.min(recent))
    resistance = float(np.max(recent))

    return {
        "trend": trend,
        "momentum": round(momentum, 2),
        "volatility": round(volatility, 2),
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "current": float(arr[-1]),
        "sma_short": round(short_ma, 2),
        "sma_long": round(long_ma, 2),
    }


def _generate_forecast_with_llm(
    asset_name: str,
    asset_type: str,
    technical: dict,
    news_context: str,
    horizon: str,
) -> dict:
    """Use LLM to generate a forecast incorporating technicals and news."""
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return _fallback_forecast(technical, horizon)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a quantitative market analyst. Generate price forecasts based on "
                "technical indicators and current news. Be specific with price targets. "
                "Respond ONLY with valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate a {horizon} forecast for {asset_name} ({asset_type}).\n\n"
                f"Technical Analysis:\n"
                f"- Current Price: {technical.get('current', 'N/A')}\n"
                f"- Trend: {technical['trend']}\n"
                f"- Momentum: {technical['momentum']}%\n"
                f"- Volatility: {technical['volatility']}%\n"
                f"- Support: {technical.get('support', 'N/A')}\n"
                f"- Resistance: {technical.get('resistance', 'N/A')}\n"
                f"- Short MA: {technical.get('sma_short', 'N/A')}\n"
                f"- Long MA: {technical.get('sma_long', 'N/A')}\n\n"
                f"Recent News Context:\n{news_context or 'No recent news available.'}\n\n"
                "Respond with JSON:\n"
                '{\n'
                '  "direction": "up" | "down" | "sideways",\n'
                '  "target_low": <number>,\n'
                '  "target_mid": <number>,\n'
                '  "target_high": <number>,\n'
                '  "confidence": <0.0-1.0>,\n'
                '  "reasoning": "<2-3 sentences>",\n'
                '  "key_drivers": ["<factor1>", "<factor2>", "<factor3>"],\n'
                '  "risk_factors": ["<risk1>", "<risk2>"]\n'
                "}"
            ),
        },
    ]

    try:
        result = chat_json(messages, temperature=0.5)
        return result
    except Exception as e:
        logger.warning("LLM forecast failed for %s: %s", asset_name, e)
        return _fallback_forecast(technical, horizon)


def _fallback_forecast(technical: dict, horizon: str) -> dict:
    """Generate a simple technical-only forecast when LLM is unavailable."""
    current = technical.get("current", 0)
    momentum = technical.get("momentum", 0)
    volatility = technical.get("volatility", 1)

    # Scale projection by horizon
    horizon_multiplier = {"weekly": 1, "monthly": 4, "quarterly": 13, "yearly": 52}.get(horizon, 4)
    projected_move = (momentum / 100) * horizon_multiplier * 0.3  # Dampened projection

    target_mid = current * (1 + projected_move)
    target_range = current * (volatility / 100) * (horizon_multiplier ** 0.5) * 0.5

    direction = "up" if projected_move > 0.005 else ("down" if projected_move < -0.005 else "sideways")

    return {
        "direction": direction,
        "target_low": round(target_mid - target_range, 2),
        "target_mid": round(target_mid, 2),
        "target_high": round(target_mid + target_range, 2),
        "confidence": round(max(0.2, min(0.8, 0.5 - volatility / 20)), 2),
        "reasoning": f"Technical forecast based on {technical['trend']} trend with {momentum:.1f}% momentum.",
        "key_drivers": [f"Trend: {technical['trend']}", f"Momentum: {momentum:.1f}%", f"Volatility: {volatility:.1f}%"],
        "risk_factors": ["No news context available", "Technical-only analysis"],
    }


def generate_prediction(
    asset_id: str,
    asset_type: str,
    prices: list[float],
    timestamps: list[int],
    news_context: str = "",
) -> dict:
    """Generate predictions for all time horizons for a single asset."""
    if asset_type == "index":
        asset_info = STOCK_INDICES.get(asset_id, {})
    elif asset_type == "crypto":
        asset_info = CRYPTO_ASSETS.get(asset_id, {})
    else:
        asset_info = FOREX_PAIRS.get(asset_id, {})

    asset_name = asset_info.get("name", asset_id)
    technical = _technical_analysis(prices)

    horizons = ["weekly", "monthly", "quarterly", "yearly"]
    predictions = {}

    for horizon in horizons:
        forecast = _generate_forecast_with_llm(asset_name, asset_type, technical, news_context, horizon)
        predictions[horizon] = {
            "horizon": horizon,
            "generated_at": datetime.utcnow().isoformat(),
            **forecast,
        }

    result = {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "asset_type": asset_type,
        "current_price": technical.get("current"),
        "technical": technical,
        "predictions": predictions,
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Track changes
    _track_prediction_change(asset_id, result)

    return result


def _prediction_hash(pred: dict) -> str:
    """Create a hash of a prediction for change detection."""
    key_data = {}
    for horizon, p in pred.get("predictions", {}).items():
        key_data[horizon] = {
            "direction": p.get("direction"),
            "target_mid": p.get("target_mid"),
        }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()


def _track_prediction_change(asset_id: str, new_prediction: dict):
    """Track prediction changes and store history."""
    new_hash = _prediction_hash(new_prediction)
    previous = _prediction_store.get(asset_id)

    change_detected = False
    changes = []

    if previous:
        old_hash = _prediction_hash(previous.get("prediction", {}))
        if old_hash != new_hash:
            change_detected = True
            # Identify what changed
            for horizon in ["weekly", "monthly", "quarterly", "yearly"]:
                old_pred = previous.get("prediction", {}).get("predictions", {}).get(horizon, {})
                new_pred = new_prediction.get("predictions", {}).get(horizon, {})
                if old_pred.get("direction") != new_pred.get("direction"):
                    changes.append({
                        "horizon": horizon,
                        "field": "direction",
                        "old": old_pred.get("direction"),
                        "new": new_pred.get("direction"),
                    })
                if old_pred.get("target_mid") and new_pred.get("target_mid"):
                    pct_change = abs(new_pred["target_mid"] - old_pred["target_mid"]) / old_pred["target_mid"] * 100
                    if pct_change > 1:  # More than 1% change in target
                        changes.append({
                            "horizon": horizon,
                            "field": "target_mid",
                            "old": old_pred.get("target_mid"),
                            "new": new_pred.get("target_mid"),
                            "pct_change": round(pct_change, 2),
                        })

    _prediction_store[asset_id] = {
        "prediction": new_prediction,
        "hash": new_hash,
        "updated_at": datetime.utcnow().isoformat(),
        "change_detected": change_detected,
        "changes": changes,
    }


def get_prediction_changes() -> list[dict]:
    """Get all assets where predictions have changed."""
    changes = []
    for asset_id, data in _prediction_store.items():
        if data.get("change_detected"):
            changes.append({
                "asset_id": asset_id,
                "updated_at": data["updated_at"],
                "changes": data["changes"],
            })
    return changes


def get_stored_prediction(asset_id: str) -> dict | None:
    """Retrieve the latest stored prediction for an asset."""
    stored = _prediction_store.get(asset_id)
    if stored:
        return stored.get("prediction")
    return None
