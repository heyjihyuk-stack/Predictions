from __future__ import annotations

"""News impact scorer - rates news articles 0-100 for market influence.

Scores are based on:
- Relevance to financial markets
- Severity/magnitude of the event
- Breadth of impact (how many markets affected)
- Historical precedent for similar events
"""

import logging
import uuid
from datetime import datetime

from app.models.domain import Article
from app.services.llm import chat_json
from config.settings import get_settings

logger = logging.getLogger(__name__)

# In-memory store for scored news
_news_store: dict[str, dict] = {}


def score_news_batch(articles: list[Article]) -> list[dict]:
    """Score a batch of news articles for market impact (0-100)."""
    if not articles:
        return []

    settings = get_settings()
    if not settings.LLM_API_KEY:
        return _fallback_scoring(articles)

    # Build context
    articles_text = ""
    for i, article in enumerate(articles[:25], 1):
        articles_text += (
            f"\n--- Article {i} ---\n"
            f"Title: {article.title}\n"
            f"Source: {article.source}\n"
            f"Category: {article.category}\n"
            f"Content: {article.text[:500]}\n"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a market impact analyst. Score each news article's potential impact "
                "on global financial markets from 0 to 100.\n\n"
                "Scoring guide:\n"
                "- 0-10: Minimal market relevance (local events, human interest)\n"
                "- 11-30: Low impact (routine reports, minor policy changes)\n"
                "- 31-50: Moderate impact (earnings reports, economic data releases)\n"
                "- 51-70: Significant impact (central bank decisions, trade policy, major earnings surprises)\n"
                "- 71-85: High impact (geopolitical escalation, financial crises, major policy shifts)\n"
                "- 86-100: Extreme impact (war, pandemic, systemic financial crisis, unprecedented policy)\n\n"
                "For each article, also identify:\n"
                "- Which markets/sectors are most affected\n"
                "- Whether the impact is positive or negative for markets\n"
                "- A brief explanation of why\n\n"
                "Respond ONLY with valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Score these {len(articles[:25])} articles for market impact:\n{articles_text}\n\n"
                "Respond with JSON:\n"
                '{\n'
                '  "scored_articles": [\n'
                '    {\n'
                '      "article_index": 1,\n'
                '      "impact_score": 65,\n'
                '      "sentiment": "negative",\n'
                '      "affected_markets": ["US Equities", "Tech Sector"],\n'
                '      "affected_forex": ["USD/JPY"],\n'
                '      "headline_summary": "Brief summary",\n'
                '      "impact_reasoning": "Why this matters for markets"\n'
                '    }\n'
                '  ]\n'
                "}"
            ),
        },
    ]

    try:
        result = chat_json(messages, temperature=0.3)
        scored = result.get("scored_articles", [])
    except Exception as e:
        logger.warning("LLM scoring failed: %s", e)
        return _fallback_scoring(articles)

    # Merge scores with article data
    output = []
    for item in scored:
        idx = item.get("article_index", 0) - 1
        if 0 <= idx < len(articles):
            article = articles[idx]
            news_id = str(uuid.uuid4())[:8]
            scored_item = {
                "id": news_id,
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "category": article.category,
                "published": article.published.isoformat() if article.published else None,
                "impact_score": min(100, max(0, item.get("impact_score", 0))),
                "sentiment": item.get("sentiment", "neutral"),
                "affected_markets": item.get("affected_markets", []),
                "affected_forex": item.get("affected_forex", []),
                "headline_summary": item.get("headline_summary", article.title),
                "impact_reasoning": item.get("impact_reasoning", ""),
                "full_text": article.text,
            }
            output.append(scored_item)
            _news_store[news_id] = scored_item

    # Sort by impact score descending
    output.sort(key=lambda x: x["impact_score"], reverse=True)
    return output


def _fallback_scoring(articles: list[Article]) -> list[dict]:
    """Simple keyword-based scoring when LLM is unavailable."""
    high_impact_keywords = [
        "war", "invasion", "crisis", "crash", "recession", "pandemic",
        "sanctions", "default", "collapse", "emergency",
    ]
    medium_keywords = [
        "fed", "central bank", "interest rate", "inflation", "gdp",
        "trade war", "tariff", "election", "summit", "oil",
    ]
    low_keywords = [
        "earnings", "quarterly", "report", "forecast", "analyst",
        "merger", "acquisition", "ipo",
    ]

    output = []
    for article in articles[:25]:
        text_lower = (article.title + " " + article.text).lower()
        score = 15  # Base score

        for kw in high_impact_keywords:
            if kw in text_lower:
                score += 25
        for kw in medium_keywords:
            if kw in text_lower:
                score += 10
        for kw in low_keywords:
            if kw in text_lower:
                score += 5

        score = min(100, score)
        news_id = str(uuid.uuid4())[:8]

        scored_item = {
            "id": news_id,
            "title": article.title,
            "source": article.source,
            "url": article.url,
            "category": article.category,
            "published": article.published.isoformat() if article.published else None,
            "impact_score": score,
            "sentiment": "neutral",
            "affected_markets": [],
            "affected_forex": [],
            "headline_summary": article.title,
            "impact_reasoning": "Scored by keyword analysis (LLM unavailable)",
            "full_text": article.text,
        }
        output.append(scored_item)
        _news_store[news_id] = scored_item

    output.sort(key=lambda x: x["impact_score"], reverse=True)
    return output


def get_news_detail(news_id: str) -> dict | None:
    """Get full details for a specific scored news item."""
    return _news_store.get(news_id)


def get_related_news(news_id: str) -> list[dict]:
    """Find news articles related to a specific scored item."""
    target = _news_store.get(news_id)
    if not target:
        return []

    related = []
    target_markets = set(target.get("affected_markets", []))
    target_category = target.get("category", "")

    for nid, item in _news_store.items():
        if nid == news_id:
            continue
        item_markets = set(item.get("affected_markets", []))
        if (item_markets & target_markets) or item.get("category") == target_category:
            related.append(item)

    related.sort(key=lambda x: x["impact_score"], reverse=True)
    return related[:10]
