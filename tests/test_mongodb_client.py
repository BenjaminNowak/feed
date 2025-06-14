import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError

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
def mock_mongodb_client():
    """Create a mock MongoDB client."""
    with patch("feed_aggregator.storage.mongodb_client.MongoClient") as mock_client:
        # Set up mock collections
        mock_feed_items = MagicMock()
        mock_metrics = MagicMock()

        # Configure mock database
        mock_db = MagicMock()
        mock_db.feed_items = mock_feed_items
        mock_db.processing_metrics = mock_metrics

        # Configure mock client
        mock_client.return_value.__getitem__.return_value = mock_db

        yield mock_client.return_value, mock_feed_items, mock_metrics


def test_init_with_credentials(mock_env_vars, mock_mongodb_client):
    """Test MongoDB client initialization with credentials."""
    with patch("feed_aggregator.storage.mongodb_client.MongoClient") as mock_client:
        MongoDBClient()
        expected_uri = "mongodb://testuser:testpass@testhost:27017/testdb"
        mock_client.assert_called_with(expected_uri)


def test_store_feed_items_success(mock_mongodb_client, sample_feed_item):
    """Test successful storage of feed items."""
    _, mock_feed_items, mock_metrics = mock_mongodb_client

    # Configure mock response
    mock_feed_items.update_one.return_value = MagicMock(
        upserted_id="new_id", modified_count=1
    )

    client = MongoDBClient()
    result = client.store_feed_items([sample_feed_item])

    assert result == 1
    mock_feed_items.update_one.assert_called_once()
    mock_metrics.insert_one.assert_called_once()


def test_store_feed_items_duplicate(mock_mongodb_client, sample_feed_item):
    """Test handling of duplicate feed items."""
    _, mock_feed_items, _ = mock_mongodb_client

    # Configure mock to raise DuplicateKeyError
    mock_feed_items.update_one.side_effect = DuplicateKeyError("Duplicate key error")

    client = MongoDBClient()
    result = client.store_feed_items([sample_feed_item])

    assert result == 0
    mock_feed_items.update_one.assert_called_once()


def test_get_pending_items(mock_mongodb_client):
    """Test retrieval of pending items."""
    _, mock_feed_items, _ = mock_mongodb_client

    # Configure mock response
    mock_feed_items.find.return_value.sort.return_value = [
        {"id": "1", "status": "pending"},
        {"id": "2", "status": "pending"},
    ]

    client = MongoDBClient()
    items = client.get_pending_items(limit=2)

    assert len(items) == 2
    mock_feed_items.find.assert_called_with({"processing_status": "pending"}, limit=2)


def test_update_item_status(mock_mongodb_client):
    """Test updating item status and LLM analysis."""
    _, mock_feed_items, _ = mock_mongodb_client

    # Configure mock response
    mock_feed_items.update_one.return_value = MagicMock(modified_count=1)

    client = MongoDBClient()
    llm_analysis = {"relevance_score": 0.8, "summary": "Test summary"}

    result = client.update_item_status("test_id", "processed", llm_analysis)

    assert result is True
    mock_feed_items.update_one.assert_called_with(
        {"id": "test_id"},
        {"$set": {"processing_status": "processed", "llm_analysis": llm_analysis}},
    )


def test_get_filtered_items(mock_mongodb_client):
    """Test retrieval of filtered items."""
    _, mock_feed_items, _ = mock_mongodb_client

    # Configure mock response
    mock_feed_items.find.return_value.sort.return_value = [
        {"id": "1", "llm_analysis": {"relevance_score": 0.9}},
        {"id": "2", "llm_analysis": {"relevance_score": 0.8}},
    ]

    client = MongoDBClient()
    items = client.get_filtered_items(min_score=0.7, limit=2)

    assert len(items) == 2
    mock_feed_items.find.assert_called_with(
        {
            "processing_status": {"$in": ["processed", "filtered_out"]},
            "llm_analysis.relevance_score": {"$gte": 0.7},
            "$or": [
                {"published_to_feed": {"$exists": False}},
                {"published_to_feed": False},
            ],
        },
        limit=2,
    )


def test_record_metric(mock_mongodb_client):
    """Test recording of processing metrics."""
    _, _, mock_metrics = mock_mongodb_client

    client = MongoDBClient()
    metadata = {"source": "test"}
    client.record_metric("items_processed", 5, metadata)

    mock_metrics.insert_one.assert_called_once()
    call_args = mock_metrics.insert_one.call_args[0][0]
    assert call_args["metric_type"] == "items_processed"
    assert call_args["value"] == 5
    assert call_args["metadata"] == metadata
    assert isinstance(call_args["timestamp"], datetime)


def test_close_connection(mock_mongodb_client):
    """Test closing MongoDB connection."""
    mock_client, _, _ = mock_mongodb_client

    client = MongoDBClient()
    client.close()

    mock_client.close.assert_called_once()
