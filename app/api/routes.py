"""Flask API routes for the predictions platform."""

import logging
from dataclasses import asdict
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory

from app.services.agents import run_simulation
from app.services.extractor import extract_entities
from app.services.fetcher import fetch_all, load_sources
from app.services.market_data import (
    FOREX_PAIRS,
    STOCK_INDICES,
    get_all_forex_summary,
    get_all_indices_summary,
    get_forex_data,
    get_index_data,
)
from app.services.news_scorer import get_news_detail, get_related_news, score_news_batch
from app.services.predictor import (
    generate_prediction,
    get_prediction_changes,
    get_stored_prediction,
)
from app.services.reporter import generate_report

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


# ── Health & Config ──────────────────────────────────────────────────

@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@api_bp.route("/sources", methods=["GET"])
def sources():
    return jsonify(load_sources())


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
        "available_indices": {k: v["name"] for k, v in STOCK_INDICES.items()},
        "available_forex": {k: v["name"] for k, v in FOREX_PAIRS.items()},
    })


# ── Predictions ──────────────────────────────────────────────────────

@api_bp.route("/predictions/<asset_type>/<asset_id>", methods=["GET"])
def get_prediction(asset_type, asset_id):
    """Get predictions for a specific asset (index or forex pair).

    asset_type: 'index' or 'forex'
    asset_id: e.g. 'sp500', 'usd_krw'
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
    """Fetch and score news articles for market impact (0-100)."""
    articles = fetch_all()
    scored = score_news_batch(articles)
    return jsonify({
        "count": len(scored),
        "articles": scored,
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
