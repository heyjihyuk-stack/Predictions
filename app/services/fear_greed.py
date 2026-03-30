from __future__ import annotations

"""Composite market Fear & Greed Index (0 = extreme fear, 100 = extreme greed).

Aggregates five components:
  1. Market Momentum  (25%)
  2. Market Volatility (25%)
  3. News Sentiment   (25%)
  4. Put/Call Ratio    (15%)
  5. Market Breadth    (10%)
"""

import logging
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# History tracking
# ---------------------------------------------------------------------------

_history_lock = threading.Lock()
_score_history: list[dict] = []  # [{timestamp, score, label, components, sentiment}]


def _record_snapshot(score: float, label: str, components: dict, sentiment: dict = None):
    """Store a timestamped snapshot for delta computation."""
    with _history_lock:
        _score_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "score": score,
            "label": label,
            "components": components,
            "sentiment": sentiment,
        })
        # Keep last 500 snapshots
        if len(_score_history) > 500:
            _score_history.pop(0)


def get_history(hours: int = 168) -> list[dict]:
    """Get score history for the last N hours (default 7 days)."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with _history_lock:
        return [s for s in _score_history if s["timestamp"] >= cutoff]


def get_deltas() -> dict:
    """Compute score changes vs previous snapshots.

    Returns dict with:
    - current: latest score
    - prev_score: previous snapshot score (or None)
    - delta_1d: change from ~24h ago (or None)
    - delta_7d: change from ~7d ago (or None)
    """
    with _history_lock:
        if not _score_history:
            return {"current": None, "prev_score": None, "delta_1d": None, "delta_7d": None}

        current = _score_history[-1]["score"]
        prev_score = _score_history[-2]["score"] if len(_score_history) >= 2 else None

        now = datetime.utcnow()
        delta_1d = None
        delta_7d = None

        # Find closest snapshot to 24h ago
        target_1d = (now - timedelta(hours=24)).isoformat()
        target_7d = (now - timedelta(days=7)).isoformat()

        for snap in reversed(_score_history):
            if delta_1d is None and snap["timestamp"] <= target_1d:
                delta_1d = round(current - snap["score"], 1)
            if delta_7d is None and snap["timestamp"] <= target_7d:
                delta_7d = round(current - snap["score"], 1)
            if delta_1d is not None and delta_7d is not None:
                break

        return {
            "current": current,
            "prev_score": prev_score,
            "delta_1d": delta_1d,
            "delta_7d": delta_7d,
        }

# ---------------------------------------------------------------------------
# Label thresholds
# ---------------------------------------------------------------------------

_LABELS = [
    (20, "Extreme Fear"),
    (40, "Fear"),
    (60, "Neutral"),
    (80, "Greed"),
    (100, "Extreme Greed"),
]


def _score_to_label(score: float) -> str:
    for threshold, label in _LABELS:
        if score <= threshold:
            return label
    return "Extreme Greed"


# ---------------------------------------------------------------------------
# Component calculators
# ---------------------------------------------------------------------------

def _compute_market_momentum(market_data: list[dict]) -> float:
    """Compare current prices to a simple 20-bar proxy.

    Each item in *market_data* should have ``current_price`` and
    ``previous_close`` (plus optionally ``ma_20``).  If ``ma_20`` is not
    supplied the change from previous close is used as a rough proxy.

    Returns a score 0-100 where >50 means bullish momentum.
    """
    if not market_data:
        return 50.0

    momentum_scores: list[float] = []
    for item in market_data:
        current = item.get("current_price")
        ma20 = item.get("ma_20")
        prev = item.get("previous_close")

        if current is None:
            continue

        if ma20 is not None and ma20 > 0:
            # Percent above / below 20-day MA, clamped to [-10%, +10%]
            pct = (current - ma20) / ma20 * 100
        elif prev is not None and prev > 0:
            pct = (current - prev) / prev * 100
        else:
            continue

        # Map [-10, +10] -> [0, 100]
        score = max(0.0, min(100.0, pct * 5 + 50))
        momentum_scores.append(score)

    return sum(momentum_scores) / len(momentum_scores) if momentum_scores else 50.0


def _compute_market_volatility(volatility_data: dict | None, market_data: list[dict]) -> float:
    """High volatility -> fear (low score), low volatility -> greed (high score).

    Uses VIX if supplied; otherwise derives from change percentages.
    Returns 0-100 (inverted: 0 = very high vol = fear).
    """
    if volatility_data:
        vix = volatility_data.get("current_vix") or volatility_data.get("implied_volatility")
        if vix is not None:
            # VIX 10 -> score ~90, VIX 30 -> ~50, VIX 50+ -> ~10
            score = max(0.0, min(100.0, 110 - vix * 2))
            return score

    # Fallback: derive from absolute change percentages in market_data
    if not market_data:
        return 50.0

    abs_changes = []
    for item in market_data:
        change = item.get("change_pct")
        if change is not None:
            abs_changes.append(abs(change))

    if not abs_changes:
        return 50.0

    avg_abs_change = sum(abs_changes) / len(abs_changes)
    # avg |change| of 0% -> 80 (calm), 3%+ -> ~20 (volatile)
    score = max(0.0, min(100.0, 80 - avg_abs_change * 20))
    return score


def _compute_news_sentiment(news_sentiment: dict) -> float:
    """Convert news sentiment percentages to 0-100 score.

    Heavily bearish press -> 0 (fear), heavily bullish -> 100 (greed).
    """
    bullish = news_sentiment.get("bullish_pct", 0)
    bearish = news_sentiment.get("bearish_pct", 0)
    neutral = news_sentiment.get("neutral_pct", 0)

    total = bullish + bearish + neutral
    if total == 0:
        return 50.0

    # Normalise
    bull_frac = bullish / total
    bear_frac = bearish / total
    # Score: pure bearish = 0, pure bullish = 100, balanced = 50
    score = (bull_frac - bear_frac + 1) / 2 * 100
    return max(0.0, min(100.0, score))


def _compute_put_call_ratio(volatility_data: dict | None) -> float | None:
    """Convert put/call ratio to a score, or return None if not available.

    P/C < 0.7 -> greed (high score), P/C > 1.2 -> fear (low score).
    """
    if not volatility_data:
        return None

    pcr = volatility_data.get("put_call_ratio")
    if pcr is None:
        return None

    # Map P/C [0.5, 1.5] -> [100, 0]
    score = max(0.0, min(100.0, (1.5 - pcr) / 1.0 * 100))
    return score


def _compute_market_breadth(market_data: list[dict]) -> float:
    """Percentage of indices that are up (positive change).

    Returns 0-100 where 100 = all up, 0 = all down.
    """
    if not market_data:
        return 50.0

    up = 0
    total = 0
    for item in market_data:
        change = item.get("change_pct")
        if change is not None:
            total += 1
            if change > 0:
                up += 1

    return (up / total * 100) if total > 0 else 50.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_fear_greed(
    market_data: list[dict],
    news_sentiment: dict,
    volatility_data: dict | None = None,
) -> dict:
    """Compute composite Fear & Greed index.

    Parameters
    ----------
    market_data:
        List of dicts, each with ``current_price``, ``previous_close``,
        ``change_pct`` (and optionally ``ma_20``).
    news_sentiment:
        Dict with ``bullish_pct``, ``bearish_pct``, ``neutral_pct``.
    volatility_data:
        Optional dict with ``current_vix`` or ``implied_volatility``
        and/or ``put_call_ratio``.

    Returns
    -------
    dict with ``score``, ``label``, and ``components``.
    """
    # Compute individual components
    momentum_score = _compute_market_momentum(market_data)
    volatility_score = _compute_market_volatility(volatility_data, market_data)
    sentiment_score = _compute_news_sentiment(news_sentiment)
    put_call_score = _compute_put_call_ratio(volatility_data)
    breadth_score = _compute_market_breadth(market_data)

    # Weights
    weights: dict[str, tuple[float, float]] = {}  # name -> (weight, score)

    weights["market_momentum"] = (0.25, momentum_score)
    weights["market_volatility"] = (0.25, volatility_score)
    weights["news_sentiment"] = (0.25, sentiment_score)

    if put_call_score is not None:
        weights["put_call_ratio"] = (0.15, put_call_score)
        weights["market_breadth"] = (0.10, breadth_score)
    else:
        # Redistribute put/call weight to other components
        weights["market_breadth"] = (0.25, breadth_score)

    # Normalise weights to sum to 1.0 (handles rounding / redistribution)
    total_weight = sum(w for w, _ in weights.values())
    composite = sum(w / total_weight * s for w, s in weights.values())
    composite = max(0.0, min(100.0, round(composite, 1)))

    components: dict[str, float] = {}
    for name, (_, score) in weights.items():
        components[name] = round(score, 1)

    label = _score_to_label(composite)

    # Record for historical tracking
    _record_snapshot(composite, label, components, news_sentiment)

    # Add deltas
    deltas = get_deltas()

    return {
        "score": composite,
        "label": label,
        "components": components,
        "delta_1d": deltas.get("delta_1d"),
        "delta_7d": deltas.get("delta_7d"),
        "prev_score": deltas.get("prev_score"),
    }
