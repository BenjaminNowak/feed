import os
from datetime import datetime
from typing import Generator, List
from unittest.mock import patch

import mongomock
import pytest
from pymongo.errors import DuplicateKeyError, OperationFailure

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


@pytest.mark.unit
@pytest.mark.parametrize(
    "test_items,expected_count",
    [
        # Empty list
        ([], 0),
        # Single item
        ([{"id": "test1", "title": "Test 1"}], 1),
        # Multiple items
        (
            [
                {"id": "test1", "title": "Test 1"},
                {"id": "test2", "title": "Test 2"},
            ],
            2,
        ),
        # Items with different statuses
        (
            [
                {"id": "test1", "processing_status": "pending"},
                {"id": "test2", "processing_status": "processed"},
            ],
            2,
        ),
        # Items with missing fields
        ([{"id": "test1"}, {"title": "No ID"}], 1),
    ],
)
def test_store_feed_items_parameterized(
    mock_mongodb_client, test_items: List[dict], expected_count: int
):
    """Test storing feed items with different scenarios."""
    stored_count = mock_mongodb_client.store_feed_items(test_items)
    assert stored_count == expected_count

    # Verify stored items
    for item in test_items:
        if "id" in item:
            stored_item = mock_mongodb_client.get_item(item["id"])
            if stored_item:
                assert stored_item["id"] == item["id"]
                if "processing_status" not in item:
                    assert stored_item["processing_status"] == "pending"


@pytest.mark.unit
@pytest.mark.parametrize(
    "error_type,error_msg",
    [
        (DuplicateKeyError, "Duplicate key error"),
        (OperationFailure, "Operation failure"),
        (Exception, "Unknown error"),
    ],
)
def test_store_feed_items_error_handling(
    mock_mongodb_client, sample_feed_item, error_type, error_msg
):
    """Test error handling during feed item storage."""
    with patch.object(
        mock_mongodb_client.feed_items, "update_one", side_effect=error_type(error_msg)
    ):
        stored_count = mock_mongodb_client.store_feed_items([sample_feed_item])
        assert stored_count == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "query_params,expected_count",
    [
        # Basic status query
        ({"status": "pending", "limit": 5}, 2),
        # With category filter
        ({"status": "processed", "category": "tech", "limit": 5}, 1),
        # With sort direction
        ({"status": "pending", "sort_direction": -1, "limit": 5}, 2),
        # With different sort field
        ({"status": "pending", "sort_field": "title", "limit": 5}, 2),
    ],
)
def test_get_items_by_status_parameterized(
    mock_mongodb_client, query_params, expected_count
):
    """Test retrieving items with different query parameters."""
    # Insert test data
    test_items = [
        {
            "id": "1",
            "title": "Test 1",
            "processing_status": "pending",
            "category": "tech",
            "published": 1000,
        },
        {
            "id": "2",
            "title": "Test 2",
            "processing_status": "pending",
            "category": "cyber",
            "published": 2000,
        },
        {
            "id": "3",
            "title": "Test 3",
            "processing_status": "processed",
            "category": "tech",
            "published": 3000,
        },
    ]
    mock_mongodb_client.store_feed_items(test_items)

    # Get items using parameters
    items = mock_mongodb_client.get_items_by_status(
        status=query_params["status"],
        category=query_params.get("category"),
        limit=query_params["limit"],
        sort_field=query_params.get("sort_field", "published"),
        sort_direction=query_params.get("sort_direction", 1),
    )

    assert len(items) == expected_count
    if query_params.get("category"):
        assert all(item["category"] == query_params["category"] for item in items)


@pytest.mark.unit
def test_complex_query_patterns(mock_mongodb_client):
    """Test MongoDB-specific query patterns."""
    # Insert test data with various fields
    test_items = [
        {
            "id": "1",
            "title": "Test 1",
            "processing_status": "processed",
            "category": "tech",
            "llm_analysis": {"relevance_score": 0.8, "keywords": ["python", "testing"]},
            "published": 1000,
            "metadata": {"source": "blog", "author": "test"},
        },
        {
            "id": "2",
            "title": "Test 2",
            "processing_status": "processed",
            "category": "tech",
            "llm_analysis": {
                "relevance_score": 0.9,
                "keywords": ["mongodb", "database"],
            },
            "published": 2000,
            "metadata": {"source": "news", "author": "test"},
        },
    ]
    mock_mongodb_client.store_feed_items(test_items)

    # Test regex query
    regex_results = list(
        mock_mongodb_client.feed_items.find({"title": {"$regex": "Test.*"}})
    )
    assert len(regex_results) == 2

    # Test nested field query
    nested_results = list(
        mock_mongodb_client.feed_items.find({"metadata.source": "blog"})
    )
    assert len(nested_results) == 1

    # Test array contains query
    array_results = list(
        mock_mongodb_client.feed_items.find(
            {"llm_analysis.keywords": {"$in": ["python"]}}
        )
    )
    assert len(array_results) == 1

    # Test compound query
    compound_results = list(
        mock_mongodb_client.feed_items.find(
            {
                "processing_status": "processed",
                "llm_analysis.relevance_score": {"$gte": 0.8},
                "metadata.author": "test",
            }
        )
    )
    assert len(compound_results) == 2
