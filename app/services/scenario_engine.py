from __future__ import annotations

"""Scenario simulation engine for 'what-if' market analysis.

Uses an LLM to project the market impact of hypothetical events.  Falls back
to keyword-based heuristics when no LLM is configured.
"""

import logging
import re

from app.services.llm import chat_json
from config.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Preset scenarios
# ---------------------------------------------------------------------------

_PRESET_SCENARIOS: list[dict] = [
    {
        "id": "fed_rate_hike",
        "description": "Fed raises rates by 50bps",
        "category": "monetary_policy",
    },
    {
        "id": "us_china_trade_war",
        "description": "US-China trade war escalation",
        "category": "geopolitics",
    },
    {
        "id": "tech_earnings_miss",
        "description": "Major tech earnings miss",
        "category": "earnings",
    },
    {
        "id": "oil_supply_shock",
        "description": "Oil supply shock",
        "category": "commodities",
    },
    {
        "id": "em_currency_crisis",
        "description": "Emerging market currency crisis",
        "category": "forex",
    },
    {
        "id": "pandemic_resurgence",
        "description": "Global pandemic resurgence",
        "category": "health",
    },
    {
        "id": "trump_tariff",
        "description": "Trump tariff announcement",
        "category": "trade_policy",
    },
    {
        "id": "mideast_conflict",
        "description": "Middle East conflict escalation",
        "category": "geopolitics",
    },
]


def get_preset_scenarios() -> list[dict]:
    """Return a list of common scenario templates."""
    return list(_PRESET_SCENARIOS)


# ---------------------------------------------------------------------------
# Keyword-based fallback heuristics
# ---------------------------------------------------------------------------

_HEURISTIC_RULES: list[dict] = [
    {
        "keywords": ["fed", "rate", "hike", "raise", "tighten", "hawkish", "bps", "basis point"],
        "market_impacts": [
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -2.5, "confidence": 0.7, "timeframe": "1-2 weeks"},
            {"market_name": "NASDAQ", "expected_direction": "down", "magnitude_pct": -3.5, "confidence": 0.7, "timeframe": "1-2 weeks"},
            {"market_name": "US Bonds", "expected_direction": "down", "magnitude_pct": -1.5, "confidence": 0.8, "timeframe": "1 week"},
        ],
        "forex_impacts": [
            {"market_name": "USD/EUR", "expected_direction": "up", "magnitude_pct": 1.5, "confidence": 0.7, "timeframe": "1 week"},
            {"market_name": "USD/JPY", "expected_direction": "up", "magnitude_pct": 1.0, "confidence": 0.6, "timeframe": "1 week"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "down", "magnitude_pct": -5.0, "confidence": 0.5, "timeframe": "1-3 days"},
        ],
        "chain_effects": [
            "Higher mortgage rates slow housing market",
            "Growth stocks face multiple compression",
            "Emerging markets face capital outflows",
        ],
        "risk_level": "medium",
        "probability": 0.6,
    },
    {
        "keywords": ["trade war", "tariff", "china", "sanction", "import duty", "trump tariff"],
        "market_impacts": [
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -3.0, "confidence": 0.7, "timeframe": "1-2 weeks"},
            {"market_name": "Shanghai Composite", "expected_direction": "down", "magnitude_pct": -4.0, "confidence": 0.7, "timeframe": "1-2 weeks"},
            {"market_name": "Hang Seng", "expected_direction": "down", "magnitude_pct": -3.5, "confidence": 0.6, "timeframe": "1-2 weeks"},
        ],
        "forex_impacts": [
            {"market_name": "USD/CNY", "expected_direction": "up", "magnitude_pct": 2.0, "confidence": 0.7, "timeframe": "1-4 weeks"},
            {"market_name": "AUD/USD", "expected_direction": "down", "magnitude_pct": -1.5, "confidence": 0.5, "timeframe": "1-2 weeks"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "up", "magnitude_pct": 3.0, "confidence": 0.4, "timeframe": "1-2 weeks"},
        ],
        "chain_effects": [
            "Supply chain disruptions raise consumer prices",
            "Export-dependent companies see margin compression",
            "Safe-haven demand boosts gold and treasuries",
        ],
        "risk_level": "high",
        "probability": 0.5,
    },
    {
        "keywords": ["tech earnings", "earnings miss", "revenue miss", "guidance cut"],
        "market_impacts": [
            {"market_name": "NASDAQ", "expected_direction": "down", "magnitude_pct": -4.0, "confidence": 0.7, "timeframe": "1-5 days"},
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -2.0, "confidence": 0.6, "timeframe": "1-5 days"},
        ],
        "forex_impacts": [
            {"market_name": "USD/JPY", "expected_direction": "down", "magnitude_pct": -0.5, "confidence": 0.4, "timeframe": "1 week"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "down", "magnitude_pct": -2.0, "confidence": 0.3, "timeframe": "1-3 days"},
        ],
        "chain_effects": [
            "Risk-off sentiment spreads to broader market",
            "Sector rotation into value/defensive stocks",
            "Venture capital funding may tighten",
        ],
        "risk_level": "medium",
        "probability": 0.55,
    },
    {
        "keywords": ["oil", "opec", "supply shock", "crude", "energy crisis", "pipeline"],
        "market_impacts": [
            {"market_name": "Crude Oil", "expected_direction": "up", "magnitude_pct": 10.0, "confidence": 0.7, "timeframe": "1-4 weeks"},
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -2.0, "confidence": 0.5, "timeframe": "1-2 weeks"},
            {"market_name": "Energy Sector", "expected_direction": "up", "magnitude_pct": 5.0, "confidence": 0.7, "timeframe": "1-2 weeks"},
        ],
        "forex_impacts": [
            {"market_name": "USD/CAD", "expected_direction": "down", "magnitude_pct": -1.5, "confidence": 0.6, "timeframe": "1-2 weeks"},
            {"market_name": "USD/RUB", "expected_direction": "down", "magnitude_pct": -3.0, "confidence": 0.5, "timeframe": "1-4 weeks"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "up", "magnitude_pct": 2.0, "confidence": 0.3, "timeframe": "1-2 weeks"},
        ],
        "chain_effects": [
            "Transportation and airline costs surge",
            "Inflation expectations rise",
            "Central banks face stagflation dilemma",
        ],
        "risk_level": "high",
        "probability": 0.45,
    },
    {
        "keywords": ["emerging market", "currency crisis", "capital flight", "sovereign debt"],
        "market_impacts": [
            {"market_name": "MSCI Emerging Markets", "expected_direction": "down", "magnitude_pct": -6.0, "confidence": 0.7, "timeframe": "1-4 weeks"},
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -1.5, "confidence": 0.5, "timeframe": "1-2 weeks"},
        ],
        "forex_impacts": [
            {"market_name": "USD/TRY", "expected_direction": "up", "magnitude_pct": 5.0, "confidence": 0.6, "timeframe": "1-4 weeks"},
            {"market_name": "USD/ZAR", "expected_direction": "up", "magnitude_pct": 4.0, "confidence": 0.5, "timeframe": "1-4 weeks"},
            {"market_name": "DXY", "expected_direction": "up", "magnitude_pct": 2.0, "confidence": 0.6, "timeframe": "1-2 weeks"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "up", "magnitude_pct": 5.0, "confidence": 0.4, "timeframe": "1-4 weeks"},
        ],
        "chain_effects": [
            "Contagion risk to other developing economies",
            "IMF intervention likely",
            "Flight to USD safe-haven assets",
        ],
        "risk_level": "high",
        "probability": 0.35,
    },
    {
        "keywords": ["pandemic", "virus", "lockdown", "quarantine", "outbreak", "covid", "WHO emergency"],
        "market_impacts": [
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -8.0, "confidence": 0.6, "timeframe": "1-4 weeks"},
            {"market_name": "Travel & Leisure", "expected_direction": "down", "magnitude_pct": -15.0, "confidence": 0.7, "timeframe": "1-4 weeks"},
            {"market_name": "Pharma/Biotech", "expected_direction": "up", "magnitude_pct": 8.0, "confidence": 0.6, "timeframe": "1-2 weeks"},
        ],
        "forex_impacts": [
            {"market_name": "USD/JPY", "expected_direction": "down", "magnitude_pct": -2.0, "confidence": 0.5, "timeframe": "1-4 weeks"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "down", "magnitude_pct": -10.0, "confidence": 0.4, "timeframe": "1-2 weeks"},
        ],
        "chain_effects": [
            "Global supply chains disrupted",
            "Central banks forced into emergency easing",
            "Remote-work / digital economy stocks benefit",
            "Tourism and hospitality severely impacted",
        ],
        "risk_level": "extreme",
        "probability": 0.2,
    },
    {
        "keywords": ["middle east", "conflict", "iran", "israel", "escalation", "military strike", "strait of hormuz"],
        "market_impacts": [
            {"market_name": "Crude Oil", "expected_direction": "up", "magnitude_pct": 8.0, "confidence": 0.7, "timeframe": "1-2 weeks"},
            {"market_name": "Gold", "expected_direction": "up", "magnitude_pct": 4.0, "confidence": 0.7, "timeframe": "1-2 weeks"},
            {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -3.0, "confidence": 0.6, "timeframe": "1-2 weeks"},
            {"market_name": "Defense Sector", "expected_direction": "up", "magnitude_pct": 5.0, "confidence": 0.6, "timeframe": "1-4 weeks"},
        ],
        "forex_impacts": [
            {"market_name": "USD/ILS", "expected_direction": "up", "magnitude_pct": 3.0, "confidence": 0.5, "timeframe": "1-2 weeks"},
            {"market_name": "CHF/EUR", "expected_direction": "up", "magnitude_pct": 1.0, "confidence": 0.5, "timeframe": "1-2 weeks"},
        ],
        "crypto_impacts": [
            {"market_name": "BTC/USD", "expected_direction": "up", "magnitude_pct": 3.0, "confidence": 0.3, "timeframe": "1-2 weeks"},
        ],
        "chain_effects": [
            "Oil shipping routes disrupted if Strait of Hormuz threatened",
            "Defense budgets increase globally",
            "Risk-off rotation into safe havens",
        ],
        "risk_level": "high",
        "probability": 0.4,
    },
]


def _fallback_scenario(scenario_description: str) -> dict:
    """Keyword-based heuristic when LLM is unavailable."""
    desc_lower = scenario_description.lower()
    best_match: dict | None = None
    best_score = 0

    for rule in _HEURISTIC_RULES:
        score = sum(1 for kw in rule["keywords"] if kw in desc_lower)
        if score > best_score:
            best_score = score
            best_match = rule

    if best_match is None or best_score == 0:
        return {
            "scenario": scenario_description,
            "probability": 0.5,
            "market_impacts": [
                {"market_name": "S&P 500", "expected_direction": "down", "magnitude_pct": -1.0, "confidence": 0.3, "timeframe": "unknown"},
            ],
            "forex_impacts": [],
            "crypto_impacts": [],
            "chain_effects": ["Insufficient data for detailed projection"],
            "recommended_actions": [
                "Monitor developments closely",
                "Consider reducing position sizes",
                "Set tighter stop-losses",
            ],
            "risk_level": "medium",
        }

    return {
        "scenario": scenario_description,
        "probability": best_match["probability"],
        "market_impacts": best_match["market_impacts"],
        "forex_impacts": best_match["forex_impacts"],
        "crypto_impacts": best_match["crypto_impacts"],
        "chain_effects": best_match["chain_effects"],
        "recommended_actions": _generate_recommendations(best_match),
        "risk_level": best_match["risk_level"],
    }


def _generate_recommendations(rule: dict) -> list[str]:
    """Derive trading recommendations from a heuristic rule."""
    recs: list[str] = []
    for impact in rule.get("market_impacts", []):
        direction = impact["expected_direction"]
        market = impact["market_name"]
        if direction == "up" and impact.get("confidence", 0) >= 0.6:
            recs.append(f"Consider long exposure to {market}")
        elif direction == "down" and impact.get("confidence", 0) >= 0.6:
            recs.append(f"Reduce or hedge {market} exposure")

    risk = rule.get("risk_level", "medium")
    if risk in ("high", "extreme"):
        recs.append("Increase cash allocation as a defensive measure")
        recs.append("Tighten stop-losses across the portfolio")

    if not recs:
        recs.append("Monitor the situation; no high-confidence trades identified")

    return recs


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_scenario(
    scenario_description: str,
    current_market_state: dict,
    knowledge_graph_summary: str | None = None,
) -> dict:
    """Simulate a scenario's market impact.

    Parameters
    ----------
    scenario_description:
        Free-text description of the hypothetical event.
    current_market_state:
        Dict with current market context (indices, prices, sentiment, etc.).
    knowledge_graph_summary:
        Optional text summarising relevant knowledge-graph context.

    Returns
    -------
    dict with scenario, probability, market/forex/crypto impacts,
    chain_effects, recommended_actions, and risk_level.
    """
    settings = get_settings()
    if not settings.LLM_API_KEY:
        logger.info("No LLM key configured, using heuristic fallback for scenario engine")
        return _fallback_scenario(scenario_description)

    # Build context for the LLM
    market_ctx = ""
    for key, value in current_market_state.items():
        market_ctx += f"- {key}: {value}\n"

    kg_section = ""
    if knowledge_graph_summary:
        kg_section = f"\nRelevant knowledge-graph context:\n{knowledge_graph_summary}\n"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert macro-economic and geopolitical analyst. Given a "
                "hypothetical scenario, estimate its impact on global financial markets, "
                "forex, and crypto.\n\n"
                "Respond ONLY with valid JSON matching this schema:\n"
                "{\n"
                '  "probability": 0.0-1.0,\n'
                '  "market_impacts": [\n'
                '    {"market_name": "...", "expected_direction": "up|down", '
                '"magnitude_pct": float, "confidence": 0.0-1.0, "timeframe": "..."}\n'
                "  ],\n"
                '  "forex_impacts": [same structure],\n'
                '  "crypto_impacts": [same structure],\n'
                '  "chain_effects": ["second-order effect 1", ...],\n'
                '  "recommended_actions": ["action 1", ...],\n'
                '  "risk_level": "low|medium|high|extreme"\n'
                "}\n\n"
                "Be specific with market names, realistic with magnitudes, and include "
                "at least 3 chain effects and 3 recommended actions."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Scenario: {scenario_description}\n\n"
                f"Current market state:\n{market_ctx}"
                f"{kg_section}\n"
                "Provide your full impact analysis as JSON."
            ),
        },
    ]

    try:
        result = chat_json(messages, temperature=0.4)

        # Validate / normalise
        risk = result.get("risk_level", "medium")
        if risk not in ("low", "medium", "high", "extreme"):
            risk = "medium"

        return {
            "scenario": scenario_description,
            "probability": max(0.0, min(1.0, float(result.get("probability", 0.5)))),
            "market_impacts": result.get("market_impacts", []),
            "forex_impacts": result.get("forex_impacts", []),
            "crypto_impacts": result.get("crypto_impacts", []),
            "chain_effects": result.get("chain_effects", []),
            "recommended_actions": result.get("recommended_actions", []),
            "risk_level": risk,
        }
    except Exception as e:
        logger.warning("LLM scenario analysis failed: %s — falling back to heuristics", e)
        return _fallback_scenario(scenario_description)
