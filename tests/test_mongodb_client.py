import os
from datetime import datetime
from typing import Generator
from unittest.mock import patch

import mongomock
import pytest

from feed_aggregator.storage.mongodb_client import MongoDBClient


@pytest.fixture
def mock_env_vars():
    """Set up test environment variables."""
    os.environ["MONGODB_HOST"] = "testhost"
    os.environ["MONGODB_PORT"] = "27017"
    os.environ["MONGODB_USERNAME"] = "testuser"
    os.environ["MONGODB_PASSWORD"] = "testpass"
    os.environ["MONGODB_DATABASE"] = "testdb"
    yield
    # Clean up
    for key in [
        "MONGODB_HOST",
        "MONGODB_PORT",
        "MONGODB_USERNAME",
        "MONGODB_PASSWORD",
        "MONGODB_DATABASE",
    ]:
        os.environ.pop(key, None)


@pytest.fixture
def sample_feed_item():
    """Create a sample feed item."""
    return {
        "fingerprint": "cce96f47",
        "id": "_my_test_key",
        "language": "en",
        "title": "Test Article",
        "published": 1749922440000,
        "crawled": 1749923258807,
        "content": {"content": "Test content", "direction": "ltr"},
    }


@pytest.fixture
def mock_mongodb_client(mock_env_vars) -> Generator[MongoDBClient, None, None]:
    """Create a MongoDB client using mongomock."""
    with mongomock.MongoClient() as client:
        # Patch MongoClient to use our mock
        with patch(
            "feed_aggregator.storage.mongodb_client.MongoClient", return_value=client
        ):
            mongodb_client = MongoDBClient()
            # Create collections
            mongodb_client.db.create_collection("feed_items")
            mongodb_client.db.create_collection("processing_metrics")
            yield mongodb_client
            # Clean up collections after each test
            mongodb_client.feed_items.delete_many({})
            mongodb_client.metrics.delete_many({})
            mongodb_client.close()


@pytest.mark.unit
def test_init_with_credentials(mock_env_vars):
    """Test MongoDB client initialization with credentials."""
    with mongomock.MongoClient() as mock_client:
        with patch(
            "feed_aggregator.storage.mongodb_client.MongoClient",
            return_value=mock_client,
        ):
            client = MongoDBClient()
            assert client.db.name == "testdb"
            client.close()


@pytest.mark.unit
def test_store_feed_items_success(mock_mongodb_client, sample_feed_item):
    """Test successful storage of feed items."""
    result = mock_mongodb_client.store_feed_items([sample_feed_item])
    assert result == 1

    # Verify item was stored
    stored_item = mock_mongodb_client.get_item(sample_feed_item["id"])
    assert stored_item is not None
    assert stored_item["id"] == sample_feed_item["id"]


@pytest.mark.unit
def test_store_feed_items_duplicate(mock_mongodb_client, sample_feed_item):
    """Test handling of duplicate feed items."""
    # First insertion
    result1 = mock_mongodb_client.store_feed_items([sample_feed_item])
    assert result1 == 1

    # Second insertion of same item
    result2 = mock_mongodb_client.store_feed_items([sample_feed_item])
    assert result2 == 0  # Should handle duplicate gracefully


@pytest.mark.unit
def test_get_pending_items(mock_mongodb_client):
    """Test retrieval of pending items."""
    # Insert test items
    items = [
        {"id": "1", "processing_status": "pending", "title": "Test 1"},
        {"id": "2", "processing_status": "pending", "title": "Test 2"},
        {"id": "3", "processing_status": "processed", "title": "Test 3"},
    ]
    mock_mongodb_client.store_feed_items(items)

    # Get pending items
    pending_items = mock_mongodb_client.get_pending_items(limit=2)
    assert len(pending_items) == 2
    assert all(item["processing_status"] == "pending" for item in pending_items)


@pytest.mark.unit
def test_update_item_status(mock_mongodb_client):
    """Test updating item status and LLM analysis."""
    # Insert test item
    item = {"id": "test_id", "title": "Test Article", "processing_status": "pending"}
    mock_mongodb_client.store_feed_items([item])

    # Update status with LLM analysis
    llm_analysis = {"relevance_score": 0.8, "summary": "Test summary"}
    result = mock_mongodb_client.update_item_status(
        "test_id", mock_mongodb_client.STATUS_PROCESSED, llm_analysis
    )

    assert result is True

    # Verify update
    updated_item = mock_mongodb_client.get_item("test_id")
    assert updated_item["processing_status"] == mock_mongodb_client.STATUS_PROCESSED
    assert updated_item["llm_analysis"] == llm_analysis


@pytest.mark.unit
def test_get_filtered_items(mock_mongodb_client):
    """Test retrieval of filtered items."""
    # Insert test items with different scores
    items = [
        {
            "id": "high_1",
            "title": "High Score 1",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.9},
            "published_to_feed": False,
        },
        {
            "id": "high_2",
            "title": "High Score 2",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.8},
            "published_to_feed": False,
        },
        {
            "id": "low_1",
            "title": "Low Score",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.5},
            "published_to_feed": False,
        },
    ]
    mock_mongodb_client.store_feed_items(items)

    # Get filtered items
    filtered_items = mock_mongodb_client.get_filtered_items(min_score=0.7, limit=2)

    assert len(filtered_items) == 2
    assert all(
        item["llm_analysis"]["relevance_score"] >= 0.7 for item in filtered_items
    )
    assert all(not item.get("published_to_feed", False) for item in filtered_items)


@pytest.mark.unit
def test_record_metric(mock_mongodb_client):
    """Test recording of processing metrics."""
    # Record test metric
    metadata = {"source": "test"}
    mock_mongodb_client.record_metric("items_processed", 5, metadata)

    # Verify metric was recorded
    metrics = list(mock_mongodb_client.metrics.find({"metric_type": "items_processed"}))
    assert len(metrics) == 1
    assert metrics[0]["metric_type"] == "items_processed"
    assert metrics[0]["value"] == 5
    assert metrics[0]["metadata"] == metadata
    assert isinstance(metrics[0]["timestamp"], datetime)


@pytest.mark.unit
def test_close_connection(mock_mongodb_client):
    """Test closing MongoDB connection."""
    # Just verify no exceptions are raised
    mock_mongodb_client.close()
