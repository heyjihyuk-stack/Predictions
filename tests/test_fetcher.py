"""Tests for the news fetcher service."""

from unittest.mock import patch, MagicMock
from datetime import datetime

from app.services.fetcher import fetch_rss, load_sources


def test_load_sources():
    sources = load_sources()
    assert isinstance(sources, dict)
    assert "rss_feeds" in sources
    assert len(sources["rss_feeds"]) > 0


@patch("app.services.fetcher.requests.get")
@patch("app.services.fetcher.atoma.parse_rss_bytes")
def test_fetch_rss_parses_entries(mock_parse, mock_get):
    mock_response = MagicMock()
    mock_response.content = b"<rss>...</rss>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    mock_item = MagicMock()
    mock_item.title = "Test Article"
    mock_item.link = "https://example.com/article"
    mock_item.description = "Test summary"
    mock_item.pub_date = datetime(2024, 3, 20, 12, 0, 0)

    mock_feed = MagicMock()
    mock_feed.title = "Test Feed"
    mock_feed.items = [mock_item]
    mock_parse.return_value = mock_feed

    articles = fetch_rss([{"url": "https://example.com/feed", "category": "test"}])
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].category == "test"
