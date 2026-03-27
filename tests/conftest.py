"""Shared test fixtures."""

import os

import pytest

# Set dummy API key for tests
os.environ.setdefault("LLM_API_KEY", "test-key")


@pytest.fixture
def app():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_articles():
    from datetime import datetime
    from app.models.domain import Article
    return [
        Article(
            url="https://example.com/1",
            title="Fed Holds Rates Steady Amid Inflation Concerns",
            text="The Federal Reserve held interest rates unchanged at 5.25-5.50%, "
                 "citing persistent inflation above the 2% target. Chair Powell noted "
                 "the committee needs more confidence before cutting rates.",
            source="Reuters",
            category="economics",
            published=datetime(2024, 3, 20),
        ),
        Article(
            url="https://example.com/2",
            title="China-Taiwan Tensions Rise After Military Drills",
            text="China conducted large-scale military exercises near Taiwan, "
                 "raising concerns about regional stability. Markets in Asia "
                 "declined on the news as investors sought safe-haven assets.",
            source="BBC News",
            category="geopolitics",
            published=datetime(2024, 3, 19),
        ),
        Article(
            url="https://example.com/3",
            title="Tech Stocks Rally on AI Earnings Beat",
            text="Major technology companies reported better-than-expected earnings "
                 "driven by AI infrastructure spending. NVIDIA and Microsoft led gains "
                 "as cloud computing demand surged.",
            source="CNBC",
            category="markets",
            published=datetime(2024, 3, 18),
        ),
    ]


@pytest.fixture
def sample_entities():
    from app.models.domain import Entity
    return [
        Entity(name="Federal Reserve", entity_type="ORGANIZATION", mentions=3,
               relationships=[("REGULATES", "US Economy")]),
        Entity(name="China", entity_type="COUNTRY", mentions=2,
               relationships=[("OPPOSES", "Taiwan")]),
        Entity(name="NVIDIA", entity_type="COMPANY", mentions=2,
               relationships=[("COMPETES_WITH", "AMD")]),
        Entity(name="S&P 500", entity_type="INDEX", mentions=1),
    ]
