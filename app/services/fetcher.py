from __future__ import annotations

"""News and market data fetching from multiple sources."""

import logging
from datetime import datetime
from pathlib import Path

import atoma
import requests
import yaml

from app.models.domain import Article
from config.settings import get_settings

logger = logging.getLogger(__name__)


def load_sources() -> dict:
    """Load source configuration from YAML."""
    settings = get_settings()
    path = Path(settings.SOURCES_FILE)
    if not path.exists():
        logger.warning("Sources file not found: %s", path)
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def fetch_rss(feeds: list[dict] | None = None) -> list[Article]:
    """Fetch articles from configured RSS feeds."""
    if feeds is None:
        sources = load_sources()
        feeds = sources.get("rss_feeds", [])

    articles = []
    for feed_cfg in feeds:
        url = feed_cfg["url"]
        category = feed_cfg.get("category", "general")
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            try:
                feed = atoma.parse_rss_bytes(resp.content)
                feed_title = feed.title or url
                for item in feed.items[:10]:
                    published = None
                    if item.pub_date:
                        published = item.pub_date.replace(tzinfo=None)

                    text = item.description or ""
                    title = item.title or "Untitled"
                    link = item.link or ""

                    articles.append(
                        Article(
                            url=link,
                            title=title,
                            text=text,
                            source=feed_title,
                            category=category,
                            published=published,
                        )
                    )
            except atoma.FeedXMLError:
                # Try Atom format
                feed = atoma.parse_atom_bytes(resp.content)
                feed_title = feed.title.value if feed.title else url
                for entry in feed.entries[:10]:
                    published = None
                    if entry.published:
                        published = entry.published.replace(tzinfo=None)
                    elif entry.updated:
                        published = entry.updated.replace(tzinfo=None)

                    text = ""
                    if entry.summary:
                        text = entry.summary.value
                    elif entry.content:
                        text = entry.content[0].value

                    title = entry.title.value if entry.title else "Untitled"
                    link = entry.links[0].href if entry.links else ""

                    articles.append(
                        Article(
                            url=link,
                            title=title,
                            text=text,
                            source=feed_title,
                            category=category,
                            published=published,
                        )
                    )
        except Exception as e:
            logger.warning("Failed to fetch RSS feed %s: %s", url, e)

    logger.info("Fetched %d articles from %d RSS feeds", len(articles), len(feeds))
    return articles


def fetch_newsapi(queries: list[dict] | None = None) -> list[Article]:
    """Fetch articles from NewsAPI.org."""
    settings = get_settings()
    if not settings.NEWSAPI_KEY:
        logger.info("NewsAPI key not configured, skipping")
        return []

    if queries is None:
        sources = load_sources()
        queries = sources.get("newsapi_queries", [])

    articles = []
    for q in queries:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": q["query"],
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                    "apiKey": settings.NEWSAPI_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("articles", []):
                published = None
                if item.get("publishedAt"):
                    try:
                        published = datetime.fromisoformat(
                            item["publishedAt"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                articles.append(
                    Article(
                        url=item.get("url", ""),
                        title=item.get("title", "Untitled"),
                        text=item.get("description", "") or item.get("content", ""),
                        source=item.get("source", {}).get("name", "NewsAPI"),
                        category=q.get("category", "general"),
                        published=published,
                    )
                )
        except Exception as e:
            logger.warning("NewsAPI fetch failed for '%s': %s", q["query"], e)

    logger.info("Fetched %d articles from NewsAPI", len(articles))
    return articles


def fetch_finnhub(symbols: list[str] | None = None) -> list[Article]:
    """Fetch market news from Finnhub."""
    settings = get_settings()
    if not settings.FINNHUB_KEY:
        logger.info("Finnhub key not configured, skipping")
        return []

    if symbols is None:
        sources = load_sources()
        symbols = sources.get("finnhub_symbols", [])

    articles = []
    for symbol in symbols:
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/company-news",
                params={
                    "symbol": symbol,
                    "from": datetime.utcnow().strftime("%Y-%m-%d"),
                    "to": datetime.utcnow().strftime("%Y-%m-%d"),
                    "token": settings.FINNHUB_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            for item in resp.json()[:5]:
                published = None
                if item.get("datetime"):
                    published = datetime.fromtimestamp(item["datetime"])
                articles.append(
                    Article(
                        url=item.get("url", ""),
                        title=item.get("headline", "Untitled"),
                        text=item.get("summary", ""),
                        source=item.get("source", "Finnhub"),
                        category="markets",
                        published=published,
                    )
                )
        except Exception as e:
            logger.warning("Finnhub fetch failed for %s: %s", symbol, e)

    logger.info("Fetched %d articles from Finnhub", len(articles))
    return articles


def fetch_all() -> list[Article]:
    """Fetch from all configured sources, deduplicate, and return."""
    all_articles = []
    all_articles.extend(fetch_rss())
    all_articles.extend(fetch_newsapi())
    all_articles.extend(fetch_finnhub())

    # Deduplicate by URL
    seen = set()
    unique = []
    for article in all_articles:
        if article.url and article.url not in seen:
            seen.add(article.url)
            unique.append(article)
        elif not article.url:
            unique.append(article)

    logger.info("Total unique articles: %d", len(unique))
    return unique
