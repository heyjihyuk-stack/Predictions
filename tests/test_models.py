"""Tests for domain models."""

from datetime import datetime

from app.models.domain import AnalystView, Article, Entity, Report


def test_article_summary_context():
    article = Article(
        url="https://example.com",
        title="Test Article",
        text="This is the article body. " * 100,
        source="Test Source",
        category="markets",
    )
    ctx = article.summary_context(100)
    assert "[Test Source | markets]" in ctx
    assert "Test Article" in ctx
    assert len(ctx) < 200  # title + truncated text


def test_entity_hash():
    e1 = Entity(name="Apple", entity_type="COMPANY")
    e2 = Entity(name="apple", entity_type="COMPANY")
    assert hash(e1) == hash(e2)


def test_analyst_view_defaults():
    view = AnalystView(
        analyst="Test",
        stance="bullish",
        prediction="Markets will rise",
        confidence=0.75,
        reasoning="Strong data",
    )
    assert view.time_horizon == "1-4 weeks"
    assert view.key_factors == []
    assert view.risks == []


def test_report_creation():
    report = Report(
        id="test-123",
        timestamp=datetime.utcnow(),
        topic="Test Topic",
        articles_analyzed=10,
        entities=[],
        views=[],
        synthesis="Test synthesis",
    )
    assert report.predictions == []
    assert report.dissenting_views == ""
