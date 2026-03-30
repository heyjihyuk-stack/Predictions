from __future__ import annotations

"""Enhanced trader persona definitions for multi-agent simulation.

Each persona represents a distinct market participant archetype with
specific strategies, biases, information sources, and risk profiles.
"""


TRADER_PERSONAS = {
    "momentum_trader": {
        "name": "Momentum Trader",
        "prompt_file": "momentum.txt",
        "strategy": "momentum",
        "risk_tolerance": "high",
        "time_horizon": "1d-2w",
        "description": (
            "Aggressive momentum trader who follows price trends and volume surges. "
            "Focuses on breakouts, relative strength, and sector rotation. "
            "Quick to cut losses, rides winners. Uses RSI, MACD, volume profile."
        ),
        "biases": ["recency_bias", "confirmation_bias", "herding"],
        "info_sources": ["price_action", "volume", "technical_indicators", "social_sentiment"],
        "weight": 0.20,
    },
    "value_investor": {
        "name": "Value Investor",
        "prompt_file": "value.txt",
        "strategy": "value",
        "risk_tolerance": "low",
        "time_horizon": "3m-1y",
        "description": (
            "Patient value investor seeking mispriced assets with margin of safety. "
            "Focuses on fundamentals: P/E, P/B, free cash flow, debt ratios. "
            "Contrarian — buys when others are fearful. Long-term conviction."
        ),
        "biases": ["anchoring_bias", "endowment_effect"],
        "info_sources": ["fundamentals", "earnings", "valuation_metrics", "macro_data"],
        "weight": 0.20,
    },
    "macro_strategist": {
        "name": "Macro Strategist",
        "prompt_file": "macro_strat.txt",
        "strategy": "macro",
        "risk_tolerance": "medium",
        "time_horizon": "1m-6m",
        "description": (
            "Top-down macro strategist analyzing central bank policy, yield curves, "
            "inflation dynamics, and cross-asset correlations. Trades rate differentials, "
            "currency flows, and regime changes. Thinks in terms of economic cycles."
        ),
        "biases": ["narrative_bias", "overconfidence"],
        "info_sources": ["central_bank", "economic_data", "yield_curves", "fx_flows", "commodity_prices"],
        "weight": 0.20,
    },
    "risk_manager": {
        "name": "Risk Manager",
        "prompt_file": "risk_mgr.txt",
        "strategy": "risk_parity",
        "risk_tolerance": "very_low",
        "time_horizon": "1w-3m",
        "description": (
            "Conservative risk manager focused on capital preservation and tail risk. "
            "Monitors VIX, correlation breakdowns, liquidity conditions, credit spreads. "
            "Always asks 'what could go wrong?' Sizes positions by risk contribution."
        ),
        "biases": ["loss_aversion", "availability_bias"],
        "info_sources": ["volatility", "correlations", "credit_spreads", "options_flow", "liquidity"],
        "weight": 0.15,
    },
    "geopolitical_analyst": {
        "name": "Geopolitical Analyst",
        "prompt_file": "geopolitical.txt",
        "strategy": "event_driven",
        "risk_tolerance": "medium",
        "time_horizon": "1d-3m",
        "description": (
            "Geopolitical specialist tracking conflicts, sanctions, elections, trade policy. "
            "Maps political events to market impacts through supply chains, energy flows, "
            "and capital flight patterns. Scenario-based thinking with probability weighting."
        ),
        "biases": ["narrative_bias", "anchoring_bias"],
        "info_sources": ["geopolitics", "news", "sanctions", "trade_policy", "defense"],
        "weight": 0.15,
    },
    "quant_analyst": {
        "name": "Quant Analyst",
        "prompt_file": "quant.txt",
        "strategy": "systematic",
        "risk_tolerance": "medium",
        "time_horizon": "1d-1m",
        "description": (
            "Data-driven quant using statistical models, mean reversion, and factor analysis. "
            "Focuses on Sharpe ratios, information ratios, and statistical significance. "
            "Skeptical of narratives — only trusts data. Looks for regime changes in correlations."
        ),
        "biases": ["model_overfitting", "data_mining_bias"],
        "info_sources": ["price_data", "statistical_models", "factor_analysis", "correlation_data"],
        "weight": 0.10,
    },
}


def get_persona(persona_id: str) -> dict:
    """Get a specific persona definition."""
    return TRADER_PERSONAS.get(persona_id, {})


def get_all_personas() -> dict:
    """Get all persona definitions."""
    return TRADER_PERSONAS


def get_weighted_consensus(predictions: list[dict]) -> dict:
    """Compute weighted consensus from multiple persona predictions.

    Each prediction dict should have: persona_id, direction, confidence, target_mid
    """
    if not predictions:
        return {"direction": "neutral", "confidence": 0, "target_mid": 0}

    total_weight = 0
    bullish_weight = 0
    bearish_weight = 0
    weighted_target = 0
    weighted_confidence = 0

    for pred in predictions:
        persona = TRADER_PERSONAS.get(pred.get("persona_id", ""), {})
        w = persona.get("weight", 0.1) * pred.get("confidence", 0.5)
        total_weight += w

        if pred.get("direction") == "up":
            bullish_weight += w
        elif pred.get("direction") == "down":
            bearish_weight += w

        weighted_target += pred.get("target_mid", 0) * w
        weighted_confidence += pred.get("confidence", 0.5) * w

    if total_weight == 0:
        return {"direction": "neutral", "confidence": 0, "target_mid": 0}

    consensus_target = weighted_target / total_weight
    consensus_confidence = weighted_confidence / total_weight

    if bullish_weight > bearish_weight * 1.2:
        direction = "up"
    elif bearish_weight > bullish_weight * 1.2:
        direction = "down"
    else:
        direction = "sideways"

    # Agreement strength: how much do personas agree?
    agreement = 1.0 - abs(bullish_weight - bearish_weight) / total_weight
    disagreement_penalty = agreement * 0.3  # Lower confidence if strong disagreement

    return {
        "direction": direction,
        "confidence": round(max(0.1, consensus_confidence - disagreement_penalty), 3),
        "target_mid": round(consensus_target, 2),
        "bullish_weight": round(bullish_weight / total_weight, 3),
        "bearish_weight": round(bearish_weight / total_weight, 3),
        "agreement_score": round(1 - agreement, 3),
        "persona_count": len(predictions),
    }
