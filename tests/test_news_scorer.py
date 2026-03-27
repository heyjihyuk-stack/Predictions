"""Tests for news impact scorer."""

from datetime import datetime

from app.models.domain import Article
from app.services.news_scorer import _fallback_scoring


def test_fallback_scoring_high_impact():
    articles = [
        Article(
            url="https://example.com/1",
            title="Global Financial Crisis Looms as Banks Collapse",
            text="A major financial crisis is unfolding as several banks face collapse. "
                 "The Federal Reserve is considering emergency measures.",
            source="Reuters",
            category="markets",
            published=datetime(2024, 3, 20),
        ),
    ]
    scored = _fallback_scoring(articles)
    assert len(scored) == 1
    assert scored[0]["impact_score"] > 30  # Should be high due to "crisis", "collapse", "fed"


def test_fallback_scoring_low_impact():
    articles = [
        Article(
            url="https://example.com/2",
            title="Local Restaurant Opens New Branch",
            text="A popular local restaurant chain opened its newest branch downtown.",
            source="Local News",
            category="general",
        ),
    ]
    scored = _fallback_scoring(articles)
    assert len(scored) == 1
    assert scored[0]["impact_score"] <= 30  # Should be low


def test_fallback_scoring_sorted():
    articles = [
        Article(url="", title="Minor Update", text="Nothing much", source="S1", category="general"),
        Article(url="", title="War Breaks Out", text="A war has started", source="S2", category="geopolitics"),
    ]
    scored = _fallback_scoring(articles)
    assert scored[0]["impact_score"] >= scored[1]["impact_score"]  # Sorted desc


def test_scored_article_has_id():
    articles = [
        Article(url="", title="Test", text="Test", source="S", category="general"),
    ]
    scored = _fallback_scoring(articles)
    assert "id" in scored[0]
    assert len(scored[0]["id"]) > 0
