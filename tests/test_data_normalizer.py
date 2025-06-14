from datetime import datetime, timezone

import pytest

from feed_aggregator.ingestion.data_normalizer import DataNormalizer


@pytest.fixture
def sample_feedly_item():
    """Sample item from Feedly API."""
    return {
        "id": "feed/1234/item/5678",
        "title": "Test Article",
        "content": {"content": "Test content", "direction": "ltr"},
        "summary": {"content": "Test summary", "direction": "ltr"},
        "author": "Test Author",
        "published": 1749922440000,  # milliseconds since epoch
        "origin": {
            "streamId": "feed/http://example.com/feed.xml",
            "title": "Example Feed",
            "htmlUrl": "http://example.com",
        },
        "alternate": [{"href": "http://example.com/article", "type": "text/html"}],
        "keywords": ["test", "article"],
        "fingerprint": "abc123",
    }


@pytest.fixture
def sample_rss_item():
    """Sample item from RSS feed."""
    return {
        "guid": "http://example.com/article",
        "title": "Test Article",
        "description": "Test content",
        "author": "Test Author",
        "pubDate": "Tue, 14 Jun 2025 14:00:00 GMT",
        "link": "http://example.com/article",
        "category": ["test", "article"],
    }


def test_normalize_feedly_item(sample_feedly_item):
    """Test normalization of Feedly item."""
    normalizer = DataNormalizer()
    result = normalizer.normalize(sample_feedly_item, source="feedly")

    assert result["source"] == "feedly"
    assert result["source_id"] == sample_feedly_item["id"]
    assert result["title"] == sample_feedly_item["title"]
    assert result["content"] == sample_feedly_item["content"]["content"]
    assert result["url"] == sample_feedly_item["alternate"][0]["href"]
    assert result["author"] == sample_feedly_item["author"]
    assert isinstance(result["published_date"], datetime)
    assert result["published_date"].tzinfo == timezone.utc
    assert isinstance(result["ingested_date"], datetime)
    assert result["tags"] == sample_feedly_item["keywords"]
    assert result["metadata"]["source_feed"] == sample_feedly_item["origin"]["title"]
    assert result["processing_status"] == "pending"
    assert "_id" in result  # Should generate a unique hash


def test_normalize_rss_item(sample_rss_item):
    """Test normalization of RSS item."""
    normalizer = DataNormalizer()
    result = normalizer.normalize(sample_rss_item, source="rss")

    assert result["source"] == "rss"
    assert result["source_id"] == sample_rss_item["guid"]
    assert result["title"] == sample_rss_item["title"]
    assert result["content"] == sample_rss_item["description"]
    assert result["url"] == sample_rss_item["link"]
    assert result["author"] == sample_rss_item["author"]
    assert isinstance(result["published_date"], datetime)
    assert result["published_date"].tzinfo == timezone.utc
    assert isinstance(result["ingested_date"], datetime)
    assert result["tags"] == sample_rss_item["category"]
    assert result["processing_status"] == "pending"
    assert "_id" in result


def test_normalize_minimal_item():
    """Test normalization with minimal required fields."""
    minimal_item = {
        "id": "12345",
        "title": "Test",
        "content": "Content",
    }

    normalizer = DataNormalizer()
    result = normalizer.normalize(minimal_item, source="test")

    assert result["source"] == "test"
    assert result["source_id"] == minimal_item["id"]
    assert result["title"] == minimal_item["title"]
    assert result["content"] == minimal_item["content"]
    assert result["url"] is None
    assert result["author"] is None
    assert isinstance(result["ingested_date"], datetime)
    assert result["tags"] == []
    assert result["processing_status"] == "pending"
    assert "_id" in result


def test_invalid_source():
    """Test handling of invalid source."""
    normalizer = DataNormalizer()
    with pytest.raises(ValueError) as exc:
        normalizer.normalize({"id": "test"}, source="invalid")
    assert "Unsupported source" in str(exc.value)


def test_missing_required_fields():
    """Test handling of missing required fields."""
    normalizer = DataNormalizer()
    with pytest.raises(ValueError) as exc:
        normalizer.normalize({"title": "Test"}, source="feedly")
    assert "Missing required field" in str(exc.value)
