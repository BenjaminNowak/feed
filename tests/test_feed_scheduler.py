from unittest.mock import MagicMock, patch

import pytest

from feed_aggregator.ingestion.feed_scheduler import FeedScheduler
from feed_aggregator.storage.mongodb_client import MongoDBClient


@pytest.fixture
def mock_mongodb():
    """Create mock MongoDB client."""
    mock = MagicMock(spec=MongoDBClient)
    mock.store_feed_items.return_value = 2
    return mock


@pytest.fixture
def mock_feedly():
    """Create mock Feedly fetcher."""
    mock = MagicMock()
    mock.get_stream_contents.return_value = {
        "id": "feed/test",
        "items": [
            {
                "id": "1",
                "title": "Test Article 1",
                "content": {"content": "Content 1"},
            },
            {
                "id": "2",
                "title": "Test Article 2",
                "content": {"content": "Content 2"},
            },
        ],
    }
    return mock


@pytest.fixture
def scheduler(mock_mongodb, mock_feedly):
    """Create FeedScheduler with mocked dependencies."""
    with patch(
        "feed_aggregator.ingestion.feed_scheduler.FeedlyFetcher"
    ) as mock_feedly_cls:
        mock_feedly_cls.return_value = mock_feedly
        scheduler = FeedScheduler(mongodb_client=mock_mongodb)
        return scheduler


def test_fetch_and_store_feedly(scheduler, mock_feedly, mock_mongodb):
    """Test fetching from Feedly and storing in MongoDB."""
    result = scheduler.fetch_and_store()

    # Verify Feedly fetcher was called
    mock_feedly.get_stream_contents.assert_called_once_with(
        "user/-/category/global.all",
        count=50,
    )

    # Verify items were normalized and stored
    mock_mongodb.store_feed_items.assert_called_once()
    stored_items = mock_mongodb.store_feed_items.call_args[0][0]
    assert len(stored_items) == 2
    assert all(item["source"] == "feedly" for item in stored_items)
    assert all("_id" in item for item in stored_items)

    # Verify metrics were recorded
    mock_mongodb.record_metric.assert_called_once_with(
        "items_fetched",
        2,
        {"source": "feedly"},
    )

    assert result == 2


def test_fetch_and_store_with_error(scheduler, mock_feedly, mock_mongodb):
    """Test handling of fetch errors."""
    # Make fetcher raise an exception
    mock_feedly.get_stream_contents.side_effect = Exception("API Error")

    result = scheduler.fetch_and_store()

    # Verify error was handled
    assert result == 0
    mock_mongodb.store_feed_items.assert_not_called()
    mock_mongodb.record_metric.assert_called_once_with(
        "fetch_error",
        1,
        {"source": "feedly", "error": "API Error"},
    )


def test_fetch_and_store_empty_response(scheduler, mock_feedly, mock_mongodb):
    """Test handling of empty response."""
    # Make fetcher return empty list
    mock_feedly.get_stream_contents.return_value = {"id": "feed/test", "items": []}

    result = scheduler.fetch_and_store()

    # Verify empty response was handled
    assert result == 0
    mock_mongodb.store_feed_items.assert_not_called()
    mock_mongodb.record_metric.assert_called_once_with(
        "items_fetched",
        0,
        {"source": "feedly"},
    )


def test_fetch_and_store_demo_mode(mock_mongodb):
    """Test fetching in demo mode."""
    with patch(
        "feed_aggregator.ingestion.feed_scheduler.FeedlyFetcher"
    ) as mock_feedly_cls:
        # Configure mock fetcher to return demo data
        mock_fetcher = MagicMock()
        mock_fetcher.get_stream_contents.return_value = {
            "id": "feed/test",
            "items": [
                {
                    "id": "demo1",
                    "title": "Demo Article",
                    "content": {"content": "Demo content"},
                },
            ],
        }
        mock_feedly_cls.return_value = mock_fetcher

        # Create scheduler in demo mode
        scheduler = FeedScheduler(mongodb_client=mock_mongodb, demo_mode=True)
        result = scheduler.fetch_and_store()

        # Verify demo mode was used
        mock_feedly_cls.assert_called_once_with(demo_mode=True)
        assert result > 0
        mock_mongodb.store_feed_items.assert_called_once()
        mock_mongodb.record_metric.assert_called_once()


def test_close(scheduler, mock_mongodb):
    """Test cleanup of resources."""
    scheduler.close()
    mock_mongodb.close.assert_called_once()
