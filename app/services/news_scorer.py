from __future__ import annotations

"""News impact scorer - rates news articles 0-100 for market influence.

Includes:
- Impact scoring (0-100)
- Market sentiment (bullish/bearish/neutral)
- News clustering (groups related stories into series)
- Sort by impact or time
"""

import logging
import re
import uuid
from datetime import datetime

from app.models.domain import Article
from app.services.llm import chat_json
from config.settings import get_settings

logger = logging.getLogger(__name__)

# In-memory store for scored news
_news_store: dict[str, dict] = {}
_clusters: list[dict] = []


def _extract_keywords(text: str) -> set[str]:
    """Extract significant keywords for clustering."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "about", "up", "out", "off", "over", "its", "it", "this", "that",
        "also", "new", "says", "said", "one", "two", "amid", "like",
    }
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    return {w for w in words if w not in stop_words}


def _compute_similarity(kw1: set[str], kw2: set[str]) -> float:
    """Jaccard similarity between keyword sets."""
    if not kw1 or not kw2:
        return 0.0
    intersection = len(kw1 & kw2)
    union = len(kw1 | kw2)
    return intersection / union if union > 0 else 0.0


def cluster_news(scored_articles: list[dict], threshold: float = 0.25) -> list[dict]:
    """Cluster related news articles into story series.

    Returns a list of clusters, each with:
    - cluster_id, cluster_label, articles (sorted by time), max_impact, sentiment
    Single articles become clusters of size 1.
    """
    if not scored_articles:
        return []

    # Extract keywords for each article
    article_keywords = []
    for a in scored_articles:
        kw = _extract_keywords(a.get("title", "") + " " + a.get("impact_reasoning", ""))
        article_keywords.append(kw)

    # Greedy clustering
    assigned = [False] * len(scored_articles)
    clusters = []

    for i, article in enumerate(scored_articles):
        if assigned[i]:
            continue

        cluster_articles = [article]
        assigned[i] = True

        for j in range(i + 1, len(scored_articles)):
            if assigned[j]:
                continue
            sim = _compute_similarity(article_keywords[i], article_keywords[j])
            # Also check if categories match for a boost
            if article.get("category") == scored_articles[j].get("category"):
                sim += 0.1
            if sim >= threshold:
                cluster_articles.append(scored_articles[j])
                assigned[j] = True

        # Sort cluster articles by published time (newest first)
        cluster_articles.sort(
            key=lambda a: a.get("published") or "0",
            reverse=True,
        )

        # Determine cluster-level stats
        max_impact = max(a["impact_score"] for a in cluster_articles)
        sentiments = [a.get("sentiment", "neutral") for a in cluster_articles]
        bullish_count = sentiments.count("positive") + sentiments.count("bullish")
        bearish_count = sentiments.count("negative") + sentiments.count("bearish")
        if bullish_count > bearish_count:
            cluster_sentiment = "bullish"
        elif bearish_count > bullish_count:
            cluster_sentiment = "bearish"
        else:
            cluster_sentiment = "neutral"

        # Use the highest-impact article's title as cluster label
        top_article = max(cluster_articles, key=lambda a: a["impact_score"])
        cluster_label = top_article.get("headline_summary") or top_article.get("title", "News")

        cluster = {
            "cluster_id": str(uuid.uuid4())[:8],
            "cluster_label": cluster_label,
            "article_count": len(cluster_articles),
            "is_series": len(cluster_articles) > 1,
            "max_impact": max_impact,
            "sentiment": cluster_sentiment,
            "articles": cluster_articles,
            "latest_published": cluster_articles[0].get("published"),
            "affected_markets": list({
                m for a in cluster_articles for m in a.get("affected_markets", [])
            }),
            "affected_forex": list({
                f for a in cluster_articles for f in a.get("affected_forex", [])
            }),
        }
        clusters.append(cluster)

    global _clusters
    _clusters = clusters
    return clusters


def score_news_batch(articles: list[Article]) -> list[dict]:
    """Score a batch of news articles for market impact (0-100)."""
    if not articles:
        return []

    settings = get_settings()
    if not settings.LLM_API_KEY:
        return _fallback_scoring(articles)

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
                "- 0-10: Minimal market relevance\n"
                "- 11-30: Low impact (routine reports)\n"
                "- 31-50: Moderate impact (economic data, earnings)\n"
                "- 51-70: Significant (central bank decisions, trade policy)\n"
                "- 71-85: High (geopolitical escalation, crises)\n"
                "- 86-100: Extreme (war, pandemic, systemic crisis)\n\n"
                "For each article, provide:\n"
                "- impact_score: 0-100\n"
                "- sentiment: 'bullish', 'bearish', or 'neutral' (market sentiment, not article tone)\n"
                "- affected_markets: list of affected markets/sectors\n"
                "- affected_forex: list of affected currency pairs\n"
                "- headline_summary: brief summary\n"
                "- impact_reasoning: why this matters\n\n"
                "Respond ONLY with valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Score these {len(articles[:25])} articles:\n{articles_text}\n\n"
                "Respond with JSON:\n"
                '{\n'
                '  "scored_articles": [\n'
                '    {\n'
                '      "article_index": 1,\n'
                '      "impact_score": 65,\n'
                '      "sentiment": "bearish",\n'
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

    output = []
    for item in scored:
        idx = item.get("article_index", 0) - 1
        if 0 <= idx < len(articles):
            article = articles[idx]
            news_id = str(uuid.uuid4())[:8]
            sentiment = item.get("sentiment", "neutral")
            # Normalize sentiment
            if sentiment in ("positive", "bullish"):
                sentiment = "bullish"
            elif sentiment in ("negative", "bearish"):
                sentiment = "bearish"
            else:
                sentiment = "neutral"

            scored_item = {
                "id": news_id,
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "category": article.category,
                "published": article.published.isoformat() if article.published else None,
                "impact_score": min(100, max(0, item.get("impact_score", 0))),
                "sentiment": sentiment,
                "affected_markets": item.get("affected_markets", []),
                "affected_forex": item.get("affected_forex", []),
                "headline_summary": item.get("headline_summary", article.title),
                "impact_reasoning": item.get("impact_reasoning", ""),
                "full_text": article.text,
            }
            output.append(scored_item)
            _news_store[news_id] = scored_item

    output.sort(key=lambda x: x["impact_score"], reverse=True)
    return output


def _detect_sentiment_keywords(text: str) -> str:
    """Keyword-based sentiment detection for fallback."""
    bullish_kw = [
        "surge", "rally", "gain", "rise", "boost", "growth", "record high",
        "bullish", "recovery", "optimism", "stimulus", "rate cut", "easing",
        "beat", "outperform", "upgrade", "deal", "agreement",
    ]
    bearish_kw = [
        "crash", "plunge", "drop", "fall", "decline", "loss", "fear",
        "bearish", "recession", "crisis", "war", "conflict", "sanction",
        "default", "collapse", "downgrade", "miss", "tariff", "threat",
    ]
    text_lower = text.lower()
    bull_score = sum(1 for kw in bullish_kw if kw in text_lower)
    bear_score = sum(1 for kw in bearish_kw if kw in text_lower)
    if bull_score > bear_score:
        return "bullish"
    elif bear_score > bull_score:
        return "bearish"
    return "neutral"


def _fallback_scoring(articles: list[Article]) -> list[dict]:
    """Keyword-based scoring with sentiment when LLM is unavailable."""
    high_impact_keywords = [
        "war", "invasion", "crisis", "crash", "recession", "pandemic",
        "sanctions", "default", "collapse", "emergency",
    ]
    medium_keywords = [
        "fed", "central bank", "interest rate", "inflation", "gdp",
        "trade war", "tariff", "election", "summit", "oil", "trump",
    ]
    low_keywords = [
        "earnings", "quarterly", "report", "forecast", "analyst",
        "merger", "acquisition", "ipo",
    ]

    output = []
    for article in articles[:25]:
        text_lower = (article.title + " " + article.text).lower()
        score = 15

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
        sentiment = _detect_sentiment_keywords(article.title + " " + article.text)

        scored_item = {
            "id": news_id,
            "title": article.title,
            "source": article.source,
            "url": article.url,
            "category": article.category,
            "published": article.published.isoformat() if article.published else None,
            "impact_score": score,
            "sentiment": sentiment,
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
    return _news_store.get(news_id)


def get_related_news(news_id: str) -> list[dict]:
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


def get_market_sentiment_summary(scored_articles: list[dict]) -> dict:
    """Compute overall market sentiment from scored articles."""
    if not scored_articles:
        return {"overall": "neutral", "score": 50, "bullish_pct": 0, "bearish_pct": 0, "neutral_pct": 100}

    # Weight sentiment by impact score
    bullish_weight = 0
    bearish_weight = 0
    neutral_weight = 0
    total_weight = 0

    for a in scored_articles:
        w = a.get("impact_score", 0)
        total_weight += w
        s = a.get("sentiment", "neutral")
        if s == "bullish":
            bullish_weight += w
        elif s == "bearish":
            bearish_weight += w
        else:
            neutral_weight += w

    if total_weight == 0:
        return {"overall": "neutral", "score": 50, "bullish_pct": 0, "bearish_pct": 0, "neutral_pct": 100}

    bullish_pct = round(bullish_weight / total_weight * 100)
    bearish_pct = round(bearish_weight / total_weight * 100)
    neutral_pct = 100 - bullish_pct - bearish_pct

    # Sentiment score: 0 = extreme bearish, 50 = neutral, 100 = extreme bullish
    sentiment_score = round(50 + (bullish_pct - bearish_pct) / 2)
    sentiment_score = max(0, min(100, sentiment_score))

    if sentiment_score >= 60:
        overall = "bullish"
    elif sentiment_score <= 40:
        overall = "bearish"
    else:
        overall = "neutral"

    return {
        "overall": overall,
        "score": sentiment_score,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "neutral_pct": neutral_pct,
        "total_articles": len(scored_articles),
    }
