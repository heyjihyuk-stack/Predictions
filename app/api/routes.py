from __future__ import annotations

"""Flask API routes for the predictions platform."""

import logging
from dataclasses import asdict
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory

from app.services.agents import run_simulation
from app.services.extractor import extract_entities
from app.services.fetcher import fetch_all, load_sources
from app.services.market_data import (
    CRYPTO_ASSETS,
    FOREX_PAIRS,
    STOCK_INDICES,
    get_all_crypto_summary,
    get_all_forex_summary,
    get_all_indices_summary,
    get_crypto_data,
    get_crypto_options,
    get_forex_data,
    get_index_data,
)
from app.services.news_scorer import (
    cluster_news,
    get_market_sentiment_summary,
    get_news_detail,
    get_related_news,
    score_news_batch,
)
from app.services.predictor import (
    generate_prediction,
    get_prediction_changes,
    get_stored_prediction,
)
from app.services.reporter import generate_report
from app.services.trading_signals import generate_trading_summary
from app.services.fear_greed import compute_fear_greed, get_history as get_fg_history
from app.services.scenario_engine import get_preset_scenarios, run_scenario
from app.services.knowledge_graph import KnowledgeGraph
from app.services.action_logger import ActionLogger

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


# ── Dashboard ────────────────────────────────────────────────────────

@api_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """All-in-one dashboard: market snapshot, sentiment, top news."""
    indices = get_all_indices_summary()
    forex = get_all_forex_summary()
    crypto = get_all_crypto_summary()

    # Fetch and score news
    articles = fetch_all()
    scored = score_news_batch(articles)
    clusters = cluster_news(scored)
    sentiment = get_market_sentiment_summary(scored)

    # Top 5 clusters by impact
    top_clusters = sorted(clusters, key=lambda c: c["max_impact"], reverse=True)[:5]

    # Fear & Greed
    options_data = {}
    try:
        from app.services.market_data import get_crypto_options
        btc_opts = get_crypto_options("btc")
        options_data["put_call_ratio"] = btc_opts.get("put_call_ratio")
        options_data["implied_volatility"] = btc_opts.get("implied_volatility")
    except Exception:
        pass
    fear_greed_data = compute_fear_greed(indices, sentiment, options_data or None)

    # Feed knowledge graph
    try:
        kg = KnowledgeGraph()
        kg.ingest_scored_news(scored)
    except Exception as e:
        logger.warning("Knowledge graph ingestion failed: %s", e)

    return jsonify({
        "indices": indices,
        "forex": forex,
        "crypto": crypto,
        "sentiment": sentiment,
        "fear_greed": fear_greed_data,
        "top_news": top_clusters,
        "total_articles": len(scored),
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── Health & Config ──────────────────────────────────────────────────

@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@api_bp.route("/sources", methods=["GET"])
def sources():
    return jsonify(load_sources())


@api_bp.route("/fear-greed/history", methods=["GET"])
def fear_greed_history():
    """Get historical Fear & Greed scores."""
    hours = int(request.args.get("hours", 168))
    return jsonify({"history": get_fg_history(hours)})


# ── Market Data ──────────────────────────────────────────────────────

@api_bp.route("/markets/indices", methods=["GET"])
def indices_summary():
    """Get current prices for all tracked stock indices."""
    return jsonify({"indices": get_all_indices_summary()})


@api_bp.route("/markets/indices/<index_id>", methods=["GET"])
def index_detail(index_id):
    """Get historical data for a specific index."""
    period = request.args.get("period", "1m")
    data = get_index_data(index_id, period)
    if "error" in data and not data.get("timestamps"):
        return jsonify(data), 404
    return jsonify(data)


@api_bp.route("/markets/forex", methods=["GET"])
def forex_summary():
    """Get current rates for all tracked forex pairs."""
    return jsonify({"forex": get_all_forex_summary()})


@api_bp.route("/markets/forex/<pair_id>", methods=["GET"])
def forex_detail(pair_id):
    """Get historical data for a specific forex pair."""
    period = request.args.get("period", "1m")
    data = get_forex_data(pair_id, period)
    if "error" in data and not data.get("timestamps"):
        return jsonify(data), 404
    return jsonify(data)


@api_bp.route("/markets/overview", methods=["GET"])
def market_overview():
    """Get a combined overview of all indices and forex pairs."""
    return jsonify({
        "indices": get_all_indices_summary(),
        "forex": get_all_forex_summary(),
        "crypto": get_all_crypto_summary(),
        "available_indices": {k: v["name"] for k, v in STOCK_INDICES.items()},
        "available_forex": {k: v["name"] for k, v in FOREX_PAIRS.items()},
        "available_crypto": {k: v["name"] for k, v in CRYPTO_ASSETS.items()},
    })


# ── Crypto ───────────────────────────────────────────────────────────

@api_bp.route("/markets/crypto", methods=["GET"])
def crypto_summary():
    """Get current prices for BTC and ETH."""
    return jsonify({"crypto": get_all_crypto_summary()})


@api_bp.route("/markets/crypto/<crypto_id>", methods=["GET"])
def crypto_detail(crypto_id):
    """Get historical data for a crypto asset."""
    period = request.args.get("period", "1m")
    data = get_crypto_data(crypto_id, period)
    if "error" in data and not data.get("timestamps"):
        return jsonify(data), 404
    return jsonify(data)


@api_bp.route("/markets/crypto/<crypto_id>/options", methods=["GET"])
def crypto_options(crypto_id):
    """Get options data for a crypto asset (from Deribit)."""
    data = get_crypto_options(crypto_id)
    if "error" in data:
        return jsonify(data), 404
    return jsonify(data)


# ── Predictions ──────────────────────────────────────────────────────

@api_bp.route("/predictions/<asset_type>/<asset_id>", methods=["GET"])
def get_prediction(asset_type, asset_id):
    """Get predictions for a specific asset.

    asset_type: 'index', 'forex', or 'crypto'
    asset_id: e.g. 'sp500', 'usd_krw', 'btc'
    """
    # Check for cached prediction first
    cached = get_stored_prediction(asset_id)
    if cached and not request.args.get("refresh"):
        return jsonify(cached)

    # Fetch market data
    period = "3m"  # Use 3 months of data for predictions
    if asset_type == "index":
        market_data = get_index_data(asset_id, period)
    elif asset_type == "forex":
        market_data = get_forex_data(asset_id, period)
    elif asset_type == "crypto":
        market_data = get_crypto_data(asset_id, period)
    else:
        return jsonify({"error": f"Unknown asset type: {asset_type}"}), 400

    prices = market_data.get("prices", [])
    timestamps = market_data.get("timestamps", [])

    if not prices:
        return jsonify({"error": "No price data available"}), 400

    # Fetch recent news for context
    news_context = ""
    try:
        articles = fetch_all()
        if articles:
            news_context = "\n".join(
                f"- {a.title} ({a.source})" for a in articles[:15]
            )
    except Exception as e:
        logger.warning("Failed to fetch news for prediction context: %s", e)

    prediction = generate_prediction(asset_id, asset_type, prices, timestamps, news_context)
    return jsonify(prediction)


@api_bp.route("/predictions/changes", methods=["GET"])
def prediction_changes():
    """Get all assets where predictions have changed."""
    return jsonify({"changes": get_prediction_changes()})


# ── News Impact ──────────────────────────────────────────────────────

@api_bp.route("/news/impact", methods=["GET"])
def news_impact():
    """Fetch, score, and cluster news articles."""
    articles = fetch_all()
    scored = score_news_batch(articles)
    clusters = cluster_news(scored)
    sentiment = get_market_sentiment_summary(scored)

    sort_by = request.args.get("sort", "impact")  # "impact" or "time"
    if sort_by == "time":
        clusters.sort(key=lambda c: c.get("latest_published") or "0", reverse=True)
    else:
        clusters.sort(key=lambda c: c["max_impact"], reverse=True)

    return jsonify({
        "count": len(scored),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "articles": scored,
        "sentiment": sentiment,
        "timestamp": datetime.utcnow().isoformat(),
    })


@api_bp.route("/news/<news_id>", methods=["GET"])
def news_detail(news_id):
    """Get full details for a scored news item, including related articles."""
    detail = get_news_detail(news_id)
    if not detail:
        return jsonify({"error": "News item not found"}), 404

    related = get_related_news(news_id)
    return jsonify({
        "article": detail,
        "related": related,
    })


# ── Full Analysis Pipeline ───────────────────────────────────────────

@api_bp.route("/fetch", methods=["POST"])
def fetch():
    articles = fetch_all()
    return jsonify({
        "count": len(articles),
        "articles": [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "category": a.category,
                "published": a.published.isoformat() if a.published else None,
            }
            for a in articles
        ],
    })


@api_bp.route("/extract", methods=["POST"])
def extract():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if text:
        from app.models.domain import Article
        articles = [
            Article(url="", title="User Input", text=text, source="manual", category="general")
        ]
    else:
        articles = fetch_all()

    entities = extract_entities(articles)
    return jsonify({
        "count": len(entities),
        "entities": [
            {
                "name": e.name,
                "type": e.entity_type,
                "mentions": e.mentions,
                "relationships": [
                    {"type": r[0], "target": r[1]} for r in e.relationships
                ],
            }
            for e in entities
        ],
    })


# ── Trading Signals ──────────────────────────────────────────────────

@api_bp.route("/signals/<asset_type>/<asset_id>", methods=["GET"])
def trading_signals(asset_type, asset_id):
    """Get technical trading signals for an asset."""
    period = "3m"
    if asset_type == "index":
        data = get_index_data(asset_id, period)
    elif asset_type == "forex":
        data = get_forex_data(asset_id, period)
    elif asset_type == "crypto":
        data = get_crypto_data(asset_id, period)
    else:
        return jsonify({"error": "Unknown asset type"}), 400

    prices = [p for p in (data.get("prices") or []) if p is not None]
    volumes = [v for v in (data.get("volumes") or []) if v is not None]
    if not prices or len(prices) < 20:
        return jsonify({"error": "Not enough price data for signals"}), 400

    summary = generate_trading_summary(prices, volumes or None)
    summary["asset_id"] = asset_id
    summary["asset_type"] = asset_type
    return jsonify(summary)


# ── Fear & Greed ─────────────────────────────────────────────────────

@api_bp.route("/fear-greed", methods=["GET"])
def fear_greed():
    """Compute composite Fear & Greed index."""
    indices = get_all_indices_summary()
    articles = fetch_all()
    scored = score_news_batch(articles)
    sentiment = get_market_sentiment_summary(scored)

    # Get crypto options for put/call ratio
    options_data = {}
    try:
        from app.services.market_data import get_crypto_options
        btc_opts = get_crypto_options("btc")
        options_data["put_call_ratio"] = btc_opts.get("put_call_ratio")
        options_data["implied_volatility"] = btc_opts.get("implied_volatility")
    except Exception:
        pass

    result = compute_fear_greed(indices, sentiment, options_data or None)
    return jsonify(result)


# ── Scenarios ────────────────────────────────────────────────────────

@api_bp.route("/scenarios", methods=["GET"])
def scenarios_list():
    """Get list of preset scenario options."""
    return jsonify({"scenarios": get_preset_scenarios()})


@api_bp.route("/scenarios/run", methods=["POST"])
def scenarios_run():
    """Run a what-if scenario analysis."""
    data = request.get_json(silent=True) or {}
    description = data.get("scenario", "")
    if not description:
        return jsonify({"error": "scenario description required"}), 400

    market_state = {}
    try:
        indices = get_all_indices_summary()
        for idx in indices[:3]:
            market_state[idx["name"]] = f"{idx.get('current_price', 'N/A')} ({idx.get('change_pct', 0):+.2f}%)"
    except Exception:
        pass

    graph_summary = None
    try:
        kg = KnowledgeGraph()
        graph_summary = kg.get_graph_summary()
    except Exception:
        pass

    result = run_scenario(description, market_state, graph_summary)
    return jsonify(result)


# ── Knowledge Graph ──────────────────────────────────────────────────

@api_bp.route("/knowledge-graph", methods=["GET"])
def knowledge_graph_summary():
    """Get knowledge graph summary."""
    kg = KnowledgeGraph()
    summary = kg.get_graph_summary()
    return jsonify(summary)


@api_bp.route("/knowledge-graph/entity/<name>", methods=["GET"])
def knowledge_graph_entity(name):
    """Get entity details and relationships from knowledge graph."""
    kg = KnowledgeGraph()
    entity = kg.get_entity(name)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404

    relationships = kg.get_relationships(name)
    impact_chain = kg.get_impact_chain(name)

    return jsonify({
        "entity": {
            "name": entity.name,
            "type": entity.entity_type,
            "mention_count": entity.mention_count,
            "first_seen": entity.first_seen.isoformat() if entity.first_seen else None,
            "last_seen": entity.last_seen.isoformat() if entity.last_seen else None,
        },
        "relationships": [
            {
                "source": e.source, "target": e.target,
                "type": e.relation_type, "weight": e.weight,
                "evidence": e.evidence[:3],
            }
            for e in relationships
        ],
        "impact_chain": impact_chain,
    })


# ── Audit Trail ──────────────────────────────────────────────────────

@api_bp.route("/audit/<asset_id>", methods=["GET"])
def audit_trail(asset_id):
    """Get prediction audit trail for an asset."""
    al = ActionLogger()
    trail = al.export_trail(asset_id)
    return jsonify({"asset_id": asset_id, "actions": trail})


# ── Full Analysis Pipeline ───────────────────────────────────────────

@api_bp.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "Global Markets and Affairs")

    logger.info("Starting analysis for topic: %s", topic)

    articles = fetch_all()
    if not articles:
        return jsonify({"error": "No articles fetched. Check your source configuration."}), 400

    topic_keywords = data.get("keywords", [])
    if topic_keywords:
        filtered = [
            a for a in articles
            if any(kw.lower() in (a.title + a.text).lower() for kw in topic_keywords)
        ]
        articles = filtered if filtered else articles

    entities = extract_entities(articles)
    sim_result = run_simulation(articles, entities)

    report = generate_report(
        topic=topic,
        articles_count=len(articles),
        entities=entities,
        views=sim_result.views,
        synthesis=sim_result.synthesis,
    )

    report_dict = asdict(report)
    report_dict["timestamp"] = report.timestamp.isoformat()
    for entity in report_dict.get("entities", []):
        entity.pop("relationships", None)

    return jsonify(report_dict)
