import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the Python path so we can import from scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import after path modification
from scripts.process_categories_runner import (  # noqa: E402
    main_runner,
    reconcile_processed_articles,
)


@pytest.fixture
def mock_mongo_client():
    with patch("scripts.process_categories_runner.MongoDBClient") as mock_client_class:
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        yield mock_client_instance


@pytest.fixture
def mock_category_config():
    with patch("scripts.process_categories_runner.CategoryConfig") as mock_config_class:
        mock_config_instance = MagicMock()
        mock_config_instance.get_global_config.return_value = {
            "default_quality_threshold": 0.6
        }
        mock_config_class.return_value = mock_config_instance
        yield mock_config_instance


@pytest.fixture
def mock_update_feed():
    with patch("scripts.process_categories_runner.update_feed_main") as mock_update:
        yield mock_update


@pytest.fixture
def mock_git_commit():
    with patch("scripts.process_categories_runner.git_commit_and_push") as mock_git:
        yield mock_git


@pytest.fixture
def mock_defused_xml():
    with patch("defusedxml.ElementTree") as mock_xml:
        yield mock_xml


@pytest.fixture
def sample_processed_articles():
    """Sample processed articles from yesterday."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    yesterday_ms = int(yesterday.timestamp() * 1000)

    return [
        {
            "id": "article_1",
            "title": "Test Article 1",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.8},
            "published": yesterday_ms,
        },
        {
            "id": "article_2",
            "title": "Test Article 2",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.7},
            "crawled": yesterday_ms,
        },
        {
            "id": "article_3",
            "title": "Test Article 3",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.9},
            "published": yesterday_ms,
        },
    ]


def test_reconcile_no_processed_articles(
    mock_mongo_client, mock_category_config, mock_update_feed, mock_git_commit
):
    """Test reconcile when no processed articles found."""
    # Mock no articles found
    mock_mongo_client.feed_items.find.return_value = []

    reconcile_processed_articles()

    # Should not call update_feed or git_commit
    mock_update_feed.assert_not_called()
    mock_git_commit.assert_not_called()
    mock_mongo_client.close.assert_called_once()


def test_reconcile_no_missing_articles(
    mock_mongo_client,
    mock_category_config,
    mock_update_feed,
    mock_git_commit,
    mock_defused_xml,
    sample_processed_articles,
):
    """Test reconcile when all processed articles are already in XML."""
    # Mock processed articles found
    mock_mongo_client.feed_items.find.return_value = sample_processed_articles

    # Mock XML parsing - all articles already in feed
    mock_tree = MagicMock()
    mock_root = MagicMock()
    mock_channel = MagicMock()

    # Create mock XML items with same IDs as processed articles
    mock_items = []
    for article in sample_processed_articles:
        mock_item = MagicMock()
        mock_guid = MagicMock()
        mock_guid.text = article["id"]
        mock_item.find.return_value = mock_guid
        mock_items.append(mock_item)

    mock_channel.findall.return_value = mock_items
    mock_root.find.return_value = mock_channel
    mock_tree.getroot.return_value = mock_root
    mock_defused_xml.parse.return_value = mock_tree

    with patch("os.path.exists", return_value=True):
        reconcile_processed_articles()

    # Should not call update_feed or git_commit since no missing articles
    mock_update_feed.assert_not_called()
    mock_git_commit.assert_not_called()
    mock_mongo_client.close.assert_called_once()


def test_reconcile_with_missing_articles(
    mock_mongo_client,
    mock_category_config,
    mock_update_feed,
    mock_git_commit,
    mock_defused_xml,
    sample_processed_articles,
):
    """Test reconcile when some processed articles are missing from XML."""
    # Mock processed articles found
    mock_mongo_client.feed_items.find.return_value = sample_processed_articles

    # Mock XML parsing - only first article in feed, others missing
    mock_tree = MagicMock()
    mock_root = MagicMock()
    mock_channel = MagicMock()

    # Only include first article in XML
    mock_item = MagicMock()
    mock_guid = MagicMock()
    mock_guid.text = sample_processed_articles[0]["id"]  # "article_1"
    mock_item.find.return_value = mock_guid
    mock_channel.findall.return_value = [mock_item]

    mock_root.find.return_value = mock_channel
    mock_tree.getroot.return_value = mock_root
    mock_defused_xml.parse.return_value = mock_tree

    # Mock update_many result
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 2  # 2 articles marked for publishing
    mock_mongo_client.feed_items.update_many.return_value = mock_update_result

    with patch("os.path.exists", return_value=True):
        reconcile_processed_articles()

    # Should mark missing articles for publishing
    mock_mongo_client.feed_items.update_many.assert_called_once_with(
        {"id": {"$in": ["article_2", "article_3"]}},
        {"$unset": {"published_to_feed": ""}},
    )

    # Should call update_feed and git_commit
    mock_update_feed.assert_called_once()
    mock_git_commit.assert_called_once()
    mock_mongo_client.close.assert_called_once()


def test_reconcile_no_existing_xml(
    mock_mongo_client,
    mock_category_config,
    mock_update_feed,
    mock_git_commit,
    sample_processed_articles,
):
    """Test reconcile when no existing XML file."""
    # Mock processed articles found
    mock_mongo_client.feed_items.find.return_value = sample_processed_articles

    # Mock update_many result
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 3  # All articles marked for publishing
    mock_mongo_client.feed_items.update_many.return_value = mock_update_result

    with patch("os.path.exists", return_value=False):
        reconcile_processed_articles()

    # Should mark all articles for publishing since no XML exists
    expected_ids = [article["id"] for article in sample_processed_articles]
    mock_mongo_client.feed_items.update_many.assert_called_once_with(
        {"id": {"$in": expected_ids}}, {"$unset": {"published_to_feed": ""}}
    )

    # Should call update_feed and git_commit
    mock_update_feed.assert_called_once()
    mock_git_commit.assert_called_once()
    mock_mongo_client.close.assert_called_once()


def test_reconcile_xml_parse_error(
    mock_mongo_client,
    mock_category_config,
    mock_update_feed,
    mock_git_commit,
    mock_defused_xml,
    sample_processed_articles,
):
    """Test reconcile when XML parsing fails."""
    # Mock processed articles found
    mock_mongo_client.feed_items.find.return_value = sample_processed_articles

    # Mock XML parsing error
    mock_defused_xml.parse.side_effect = Exception("XML parse error")

    # Mock update_many result
    mock_update_result = MagicMock()
    mock_update_result.modified_count = 3  # All articles marked for publishing
    mock_mongo_client.feed_items.update_many.return_value = mock_update_result

    with patch("os.path.exists", return_value=True):
        reconcile_processed_articles()

    # Should treat as if no XML exists and mark all articles for publishing
    expected_ids = [article["id"] for article in sample_processed_articles]
    mock_mongo_client.feed_items.update_many.assert_called_once_with(
        {"id": {"$in": expected_ids}}, {"$unset": {"published_to_feed": ""}}
    )

    # Should call update_feed and git_commit
    mock_update_feed.assert_called_once()
    mock_git_commit.assert_called_once()
    mock_mongo_client.close.assert_called_once()


def test_main_runner_reconcile_option():
    """Test main_runner with --reconcile option."""
    with patch(
        "scripts.process_categories_runner.reconcile_processed_articles"
    ) as mock_reconcile:
        with patch("sys.argv", ["process_categories_runner.py", "--reconcile"]):
            main_runner()

        mock_reconcile.assert_called_once()


def test_main_runner_reconcile_with_categories_error():
    """Test main_runner with --reconcile and categories should error."""
    with patch("sys.argv", ["process_categories_runner.py", "--reconcile", "ML"]):
        with patch("sys.exit", side_effect=SystemExit) as mock_exit:
            with patch(
                "scripts.process_categories_runner.reconcile_processed_articles"
            ) as mock_reconcile:
                with pytest.raises(SystemExit):
                    main_runner()

        mock_exit.assert_called_once_with(1)
        mock_reconcile.assert_not_called()


def test_main_runner_reconcile_with_all_error():
    """Test main_runner with --reconcile and --all should error."""
    with patch("sys.argv", ["process_categories_runner.py", "--reconcile", "--all"]):
        with patch("sys.exit", side_effect=SystemExit) as mock_exit:
            with patch(
                "scripts.process_categories_runner.reconcile_processed_articles"
            ) as mock_reconcile:
                with pytest.raises(SystemExit):
                    main_runner()

        mock_exit.assert_called_once_with(1)
        mock_reconcile.assert_not_called()
