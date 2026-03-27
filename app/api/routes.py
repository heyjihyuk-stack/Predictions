"""Flask API routes for the predictions platform."""

import logging
from dataclasses import asdict
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.services.agents import run_simulation
from app.services.extractor import extract_entities
from app.services.fetcher import fetch_all, load_sources
from app.services.reporter import generate_report

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@api_bp.route("/sources", methods=["GET"])
def sources():
    """List configured news and data sources."""
    return jsonify(load_sources())


@api_bp.route("/fetch", methods=["POST"])
def fetch():
    """Fetch articles from all configured sources."""
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
    """Extract entities from provided text or fetched articles."""
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
    """Full pipeline: fetch news, extract entities, run multi-agent simulation, generate report."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "Global Markets and Affairs")

    logger.info("Starting analysis for topic: %s", topic)

    # 1. Fetch
    articles = fetch_all()
    if not articles:
        return jsonify({"error": "No articles fetched. Check your source configuration."}), 400

    # Optional: filter by topic keywords
    topic_keywords = data.get("keywords", [])
    if topic_keywords:
        filtered = [
            a for a in articles
            if any(kw.lower() in (a.title + a.text).lower() for kw in topic_keywords)
        ]
        articles = filtered if filtered else articles  # Fall back to all if no matches

    # 2. Extract entities
    entities = extract_entities(articles)

    # 3. Run multi-agent simulation
    sim_result = run_simulation(articles, entities)

    # 4. Generate report
    report = generate_report(
        topic=topic,
        articles_count=len(articles),
        entities=entities,
        views=sim_result.views,
        synthesis=sim_result.synthesis,
    )

    # Serialize
    report_dict = asdict(report)
    # Fix datetime serialization
    report_dict["timestamp"] = report.timestamp.isoformat()
    for entity in report_dict.get("entities", []):
        entity.pop("relationships", None)  # Simplify for JSON
    for view in report_dict.get("views", []):
        pass  # Already serializable

    return jsonify(report_dict)
