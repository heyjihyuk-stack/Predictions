from __future__ import annotations

"""Trading signals service with technical indicators for trading decisions.

Provides RSI, MACD, Bollinger Bands, support/resistance detection,
composite signal generation, and full trading summaries.
"""

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_array(prices: list[float]) -> np.ndarray:
    """Convert to float64 ndarray, replacing None with NaN."""
    return np.asarray(prices, dtype=np.float64)


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average (same length as input, NaN-filled warmup)."""
    out = np.full_like(data, np.nan)
    if len(data) < period:
        return out
    # Seed with SMA
    out[period - 1] = np.mean(data[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(data)):
        out[i] = (data[i] - out[i - 1]) * multiplier + out[i - 1]
    return out


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple moving average (NaN-filled warmup)."""
    out = np.full_like(data, np.nan)
    if len(data) < period:
        return out
    cumsum = np.cumsum(data)
    out[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:-period]])[: len(data) - period + 1]) / period
    return out


# ---------------------------------------------------------------------------
# Technical Indicators
# ---------------------------------------------------------------------------

def compute_rsi(prices: list[float], period: int = 14) -> list[float]:
    """Compute Relative Strength Index.

    Returns a list the same length as *prices* with NaN for warmup periods.
    """
    arr = _ensure_array(prices)
    out = np.full(len(arr), np.nan)
    if len(arr) < period + 1:
        return out.tolist()

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i + 1] = 100.0 - 100.0 / (1.0 + rs)

    return out.tolist()


def compute_macd(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, list[float]]:
    """Compute MACD, signal line, and histogram."""
    arr = _ensure_array(prices)
    fast_ema = _ema(arr, fast)
    slow_ema = _ema(arr, slow)
    macd_line = fast_ema - slow_ema
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd": macd_line.tolist(),
        "signal": signal_line.tolist(),
        "histogram": histogram.tolist(),
    }


def compute_bollinger(
    prices: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, list[float]]:
    """Compute Bollinger Bands (upper, middle, lower)."""
    arr = _ensure_array(prices)
    middle = _sma(arr, period)

    std = np.full_like(arr, np.nan)
    for i in range(period - 1, len(arr)):
        std[i] = np.std(arr[i - period + 1 : i + 1], ddof=0)

    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return {
        "upper": upper.tolist(),
        "middle": middle.tolist(),
        "lower": lower.tolist(),
    }


def find_support_resistance(
    prices: list[float],
    window: int = 20,
) -> dict[str, list[float]]:
    """Identify local support and resistance levels using rolling min/max pivots."""
    arr = _ensure_array(prices)
    supports: list[float] = []
    resistances: list[float] = []

    if len(arr) < window:
        return {"support": supports, "resistance": resistances}

    half = window // 2
    for i in range(half, len(arr) - half):
        segment = arr[i - half : i + half + 1]
        if arr[i] == np.nanmin(segment):
            supports.append(float(arr[i]))
        elif arr[i] == np.nanmax(segment):
            resistances.append(float(arr[i]))

    # Deduplicate close levels (within 0.5% of each other)
    supports = _deduplicate_levels(supports)
    resistances = _deduplicate_levels(resistances)

    return {"support": supports, "resistance": resistances}


def _deduplicate_levels(levels: list[float], tolerance: float = 0.005) -> list[float]:
    """Merge levels that are within *tolerance* fraction of each other."""
    if not levels:
        return levels
    sorted_levels = sorted(levels)
    merged = [sorted_levels[0]]
    for lvl in sorted_levels[1:]:
        if merged[-1] == 0 or abs(lvl - merged[-1]) / abs(merged[-1]) > tolerance:
            merged.append(lvl)
        else:
            merged[-1] = (merged[-1] + lvl) / 2.0
    return merged


# ---------------------------------------------------------------------------
# Signal Detection
# ---------------------------------------------------------------------------

def detect_signals(
    prices: list[float],
    volumes: list[float] | None = None,
) -> list[dict]:
    """Detect trading signals from technical indicators.

    Each signal dict contains:
      type, signal_name, strength, price_at_signal, reasoning
    """
    if len(prices) < 2:
        return []

    signals: list[dict] = []
    current_price = prices[-1]

    # --- RSI signals ---
    rsi_values = compute_rsi(prices)
    rsi_latest = rsi_values[-1] if not math.isnan(rsi_values[-1]) else None

    if rsi_latest is not None:
        if rsi_latest <= 30:
            strength = min(100, int((30 - rsi_latest) / 30 * 100))
            signals.append({
                "type": "BUY",
                "signal_name": "RSI_OVERSOLD",
                "strength": strength,
                "price_at_signal": current_price,
                "reasoning": f"RSI at {rsi_latest:.1f} indicates oversold conditions",
            })
        elif rsi_latest >= 70:
            strength = min(100, int((rsi_latest - 70) / 30 * 100))
            signals.append({
                "type": "SELL",
                "signal_name": "RSI_OVERBOUGHT",
                "strength": strength,
                "price_at_signal": current_price,
                "reasoning": f"RSI at {rsi_latest:.1f} indicates overbought conditions",
            })

    # --- MACD signals ---
    macd_data = compute_macd(prices)
    macd_line = macd_data["macd"]
    signal_line = macd_data["signal"]

    if len(macd_line) >= 2 and not (math.isnan(macd_line[-1]) or math.isnan(macd_line[-2])
                                     or math.isnan(signal_line[-1]) or math.isnan(signal_line[-2])):
        prev_diff = macd_line[-2] - signal_line[-2]
        curr_diff = macd_line[-1] - signal_line[-1]

        if prev_diff <= 0 < curr_diff:
            strength = min(100, int(abs(curr_diff) / (abs(current_price) * 0.01) * 50)) if current_price else 50
            signals.append({
                "type": "BUY",
                "signal_name": "MACD_CROSSOVER",
                "strength": min(strength, 100),
                "price_at_signal": current_price,
                "reasoning": "MACD crossed above signal line (bullish crossover)",
            })
        elif prev_diff >= 0 > curr_diff:
            strength = min(100, int(abs(curr_diff) / (abs(current_price) * 0.01) * 50)) if current_price else 50
            signals.append({
                "type": "SELL",
                "signal_name": "MACD_CROSSOVER",
                "strength": min(strength, 100),
                "price_at_signal": current_price,
                "reasoning": "MACD crossed below signal line (bearish crossover)",
            })

    # --- Bollinger Band signals ---
    bb = compute_bollinger(prices)
    upper = bb["upper"][-1] if not math.isnan(bb["upper"][-1]) else None
    lower = bb["lower"][-1] if not math.isnan(bb["lower"][-1]) else None
    middle = bb["middle"][-1] if not math.isnan(bb["middle"][-1]) else None

    if lower is not None and current_price <= lower:
        band_width = (upper - lower) if upper and lower else 1
        pct_below = (lower - current_price) / band_width * 100 if band_width else 50
        signals.append({
            "type": "BUY",
            "signal_name": "BOLLINGER_BOUNCE",
            "strength": min(100, max(10, int(pct_below * 2 + 40))),
            "price_at_signal": current_price,
            "reasoning": f"Price at/below lower Bollinger Band ({lower:.2f}), potential bounce",
        })
    elif upper is not None and current_price >= upper:
        band_width = (upper - lower) if upper and lower else 1
        pct_above = (current_price - upper) / band_width * 100 if band_width else 50
        signals.append({
            "type": "SELL",
            "signal_name": "BOLLINGER_BOUNCE",
            "strength": min(100, max(10, int(pct_above * 2 + 40))),
            "price_at_signal": current_price,
            "reasoning": f"Price at/above upper Bollinger Band ({upper:.2f}), potential pullback",
        })

    # --- Volume spike (if available) ---
    if volumes and len(volumes) >= 20:
        vol_arr = np.asarray(volumes, dtype=np.float64)
        avg_vol = np.mean(vol_arr[-20:])
        if avg_vol > 0 and vol_arr[-1] > avg_vol * 2:
            # Volume spike - amplify existing signals or flag it
            change = prices[-1] - prices[-2] if len(prices) >= 2 else 0
            sig_type = "BUY" if change > 0 else "SELL" if change < 0 else "HOLD"
            signals.append({
                "type": sig_type,
                "signal_name": "VOLUME_SPIKE",
                "strength": min(100, int((vol_arr[-1] / avg_vol - 1) * 30)),
                "price_at_signal": current_price,
                "reasoning": f"Volume spike ({vol_arr[-1]:.0f} vs avg {avg_vol:.0f}) confirms price move",
            })

    # If no signals, return HOLD
    if not signals:
        signals.append({
            "type": "HOLD",
            "signal_name": "NO_SIGNAL",
            "strength": 0,
            "price_at_signal": current_price,
            "reasoning": "No clear technical signal detected",
        })

    return signals


# ---------------------------------------------------------------------------
# Trading Summary
# ---------------------------------------------------------------------------

def generate_trading_summary(
    prices: list[float],
    volumes: list[float] | None = None,
) -> dict:
    """Generate a comprehensive trading summary combining all indicators."""
    if len(prices) < 2:
        return {
            "current_price": prices[-1] if prices else None,
            "trend": "sideways",
            "rsi_value": None,
            "rsi_signal": "neutral",
            "macd_signal": "neutral",
            "bollinger_position": "middle",
            "support_levels": [],
            "resistance_levels": [],
            "active_signals": [],
            "overall_bias": "neutral",
            "bias_strength": 0,
            "suggested_action": {
                "action": "HOLD",
                "entry_zone": None,
                "stop_loss": None,
                "take_profit": None,
                "risk_reward_ratio": None,
            },
        }

    current_price = prices[-1]

    # --- Trend ---
    if len(prices) >= 20:
        sma20 = np.mean(prices[-20:])
        sma50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma20
        if current_price > sma20 > sma50:
            trend = "up"
        elif current_price < sma20 < sma50:
            trend = "down"
        else:
            trend = "sideways"
    else:
        trend = "up" if prices[-1] > prices[0] else "down" if prices[-1] < prices[0] else "sideways"

    # --- RSI ---
    rsi_values = compute_rsi(prices)
    rsi_latest = rsi_values[-1] if not math.isnan(rsi_values[-1]) else None
    if rsi_latest is not None:
        if rsi_latest >= 70:
            rsi_signal = "overbought"
        elif rsi_latest <= 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"
    else:
        rsi_signal = "neutral"

    # --- MACD ---
    macd_data = compute_macd(prices)
    macd_line = macd_data["macd"]
    sig_line = macd_data["signal"]
    if not math.isnan(macd_line[-1]) and not math.isnan(sig_line[-1]):
        if macd_line[-1] > sig_line[-1]:
            macd_signal = "bullish"
        elif macd_line[-1] < sig_line[-1]:
            macd_signal = "bearish"
        else:
            macd_signal = "neutral"
    else:
        macd_signal = "neutral"

    # --- Bollinger position ---
    bb = compute_bollinger(prices)
    bb_upper = bb["upper"][-1]
    bb_lower = bb["lower"][-1]
    if not math.isnan(bb_upper) and not math.isnan(bb_lower):
        if current_price >= bb_upper:
            bollinger_position = "above_upper"
        elif current_price <= bb_lower:
            bollinger_position = "below_lower"
        else:
            bollinger_position = "middle"
    else:
        bollinger_position = "middle"

    # --- Support / Resistance ---
    sr = find_support_resistance(prices)
    support_levels = sr["support"]
    resistance_levels = sr["resistance"]

    # Nearest levels
    nearest_support = max((s for s in support_levels if s < current_price), default=None)
    nearest_resistance = min((r for r in resistance_levels if r > current_price), default=None)

    # --- Signals ---
    active_signals = detect_signals(prices, volumes)

    # --- Overall bias ---
    bullish_score = 0
    bearish_score = 0

    # Trend contribution (30 pts)
    if trend == "up":
        bullish_score += 30
    elif trend == "down":
        bearish_score += 30

    # RSI contribution (20 pts)
    if rsi_signal == "oversold":
        bullish_score += 20
    elif rsi_signal == "overbought":
        bearish_score += 20

    # MACD contribution (25 pts)
    if macd_signal == "bullish":
        bullish_score += 25
    elif macd_signal == "bearish":
        bearish_score += 25

    # Bollinger contribution (15 pts)
    if bollinger_position == "below_lower":
        bullish_score += 15  # mean-reversion potential
    elif bollinger_position == "above_upper":
        bearish_score += 15

    # Signal contribution (10 pts)
    for sig in active_signals:
        if sig["type"] == "BUY":
            bullish_score += 10 * sig["strength"] / 100
        elif sig["type"] == "SELL":
            bearish_score += 10 * sig["strength"] / 100

    total = bullish_score + bearish_score
    if total == 0:
        overall_bias = "neutral"
        bias_strength = 0
    else:
        net = bullish_score - bearish_score
        bias_strength = min(100, int(abs(net)))
        if net > 10:
            overall_bias = "bullish"
        elif net < -10:
            overall_bias = "bearish"
        else:
            overall_bias = "neutral"

    # --- Suggested action ---
    if overall_bias == "bullish":
        action = "BUY"
        entry_zone = (
            nearest_support or current_price * 0.98,
            current_price,
        )
        stop_loss = nearest_support * 0.98 if nearest_support else current_price * 0.95
        take_profit = nearest_resistance if nearest_resistance else current_price * 1.05
    elif overall_bias == "bearish":
        action = "SELL"
        entry_zone = (
            current_price,
            nearest_resistance or current_price * 1.02,
        )
        stop_loss = nearest_resistance * 1.02 if nearest_resistance else current_price * 1.05
        take_profit = nearest_support if nearest_support else current_price * 0.95
    else:
        action = "HOLD"
        entry_zone = None
        stop_loss = None
        take_profit = None

    # Risk/Reward
    if stop_loss and take_profit and action != "HOLD":
        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        risk_reward_ratio = round(reward / risk, 2) if risk > 0 else None
    else:
        risk_reward_ratio = None

    return {
        "current_price": current_price,
        "trend": trend,
        "rsi_value": round(rsi_latest, 2) if rsi_latest is not None else None,
        "rsi_signal": rsi_signal,
        "macd_signal": macd_signal,
        "bollinger_position": bollinger_position,
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "active_signals": active_signals,
        "overall_bias": overall_bias,
        "bias_strength": bias_strength,
        "suggested_action": {
            "action": action,
            "entry_zone": entry_zone,
            "stop_loss": round(stop_loss, 4) if stop_loss else None,
            "take_profit": round(take_profit, 4) if take_profit else None,
            "risk_reward_ratio": risk_reward_ratio,
        },
    }
