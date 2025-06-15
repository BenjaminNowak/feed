import os
import subprocess
from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest
import responses

from feed_aggregator.etl.process_category import (
    _clean_item_data,
    git_commit_and_push,
    main,
)


# Test data fixtures
@pytest.fixture
def test_items():
    def _create_items(count):
        return [
            {
                "id": f"test_id_{i}",
                "title": f"Test Article {i}",
                "content": {"content": "test content"},
                "summary": {"content": "test summary"},
            }
            for i in range(count)
        ]

    return _create_items


@pytest.fixture
def mock_feedly_session():
    with patch("feedly.api_client.session.FeedlySession") as mock_session_class:
        # Create a mock session instance that behaves like a real FeedlySession
        mock_session_instance = MagicMock()

        # Mock the user and categories structure
        mock_user = MagicMock()
        mock_categories = MagicMock()
        mock_categories.name2stream = {"ML": "stream_id"}
        mock_categories.get = MagicMock(return_value=mock_categories)
        mock_categories.keys = MagicMock(return_value=["ML"])
        mock_user.user_categories = mock_categories
        mock_session_instance.user = mock_user

        # Mock the auth token and user_id
        mock_session_instance.auth = "test_token"
        mock_session_instance.user_id = "test_user"

        # Make the class constructor return our mock instance
        mock_session_class.return_value = mock_session_instance

        yield mock_session_instance


@pytest.fixture
def setup_env_vars():
    os.environ["FEEDLY_TOKEN"] = "test_token"
    os.environ["FEEDLY_USER"] = "test_user"
    yield
    del os.environ["FEEDLY_TOKEN"]
    del os.environ["FEEDLY_USER"]


@pytest.fixture
def mock_subprocess():
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_update_feed():
    with patch("feed_aggregator.etl.update_feed.main") as mock_main:
        yield mock_main


@pytest.fixture
def mock_git_commit():
    with patch("feed_aggregator.etl.process_category.git_commit_and_push") as mock_git:
        yield mock_git


def test_git_commit_and_push_success(mock_subprocess):
    # Mock datetime to get consistent timestamp
    current_time = datetime(2025, 6, 14, 16, 26, 29)
    expected_timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
    expected_msg = f"Update feed: {expected_timestamp}"

    with patch("feed_aggregator.etl.process_category.datetime") as mock_datetime:
        mock_datetime.now.return_value = current_time
        git_commit_and_push()

    # Verify the exact sequence of git commands
    mock_subprocess.assert_has_calls(
        [
            call(["git", "add", "feed.xml"], check=True),
            call(["git", "commit", "-m", expected_msg], check=True),
            call(["git", "push"], check=True),
        ]
    )


def test_git_commit_and_push_failure(mock_subprocess):
    mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")

    # Should not raise exception but print error
    git_commit_and_push()
    assert mock_subprocess.called


@pytest.fixture
def mock_dependencies(mock_feedly_session):
    with patch(
        "feed_aggregator.etl.process_category.FeedlyFetcher"
    ) as mock_fetcher, patch(
        "feed_aggregator.etl.process_category.ContentAnalyzer"
    ) as mock_analyzer, patch(
        "feed_aggregator.etl.process_category.LLMFilter"
    ) as mock_llm, patch(
        "feed_aggregator.etl.process_category.MongoDBClient"
    ) as mock_mongo, patch(
        "feed_aggregator.etl.process_category.CategoryConfig"
    ) as mock_category_config:
        # Setup mock fetcher
        mock_fetcher_instance = mock_fetcher.return_value
        mock_fetcher_instance.token = "test_token"
        mock_fetcher_instance.user_id = "test_user"
        mock_fetcher_instance.session = mock_feedly_session
        mock_fetcher_instance.get_stream_contents = MagicMock()
        mock_fetcher_instance.get_stream_contents.return_value = {"items": []}

        # Setup mock analyzer
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_item = MagicMock()
        mock_analyzer_instance.analyze_item.return_value = {"content_analysis": "test"}

        # Setup mock LLM
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_item = MagicMock()
        mock_llm_instance.analyze_item.return_value = {"relevance_score": 0.5}

        # Setup mock mongo
        mock_mongo_instance = mock_mongo.return_value
        mock_mongo_instance.get_item.return_value = None
        mock_mongo_instance.item_exists.return_value = False
        mock_mongo_instance.store_feed_items = MagicMock()
        mock_mongo_instance.update_item = MagicMock()
        mock_mongo_instance.get_items_by_status.return_value = (
            []
        )  # Default empty result
        mock_mongo_instance.get_filtered_items.return_value = []
        mock_mongo_instance.close = MagicMock()
        mock_mongo_instance.STATUS_PENDING = "pending"
        mock_mongo_instance.STATUS_PROCESSED = "processed"
        mock_mongo_instance.STATUS_FILTERED = "filtered_out"

        # Setup mock category config
        mock_config_instance = mock_category_config.return_value
        mock_config_instance.get_quality_threshold.return_value = 0.6
        mock_config_instance.get_high_quality_target.return_value = 10
        mock_config_instance.get_output_feed.return_value = "feed.xml"
        mock_config_instance.get_feedly_category.return_value = "ML"

        yield {
            "fetcher": mock_fetcher_instance,
            "analyzer": mock_analyzer_instance,
            "llm": mock_llm_instance,
            "mongo": mock_mongo_instance,
            "config": mock_config_instance,
        }


def test_main_high_quality_articles(
    mock_dependencies,
    mock_update_feed,
    mock_git_commit,
    mock_feedly_session,
    setup_env_vars,
    test_items,
):
    # Setup test data
    items = test_items(15)
    mock_dependencies["fetcher"].get_stream_contents.return_value = {"items": items}

    # Mock MongoDB behavior for the new flow:
    # 1. First, item_exists returns False for all items (they don't exist yet)
    # 2. Then, get_items_by_status returns the items as pending for processing
    pending_items = [
        {**item, "category": "ML", "processing_status": "pending"} for item in items
    ]

    # Mock MongoDB methods properly for the 3-step flow
    mock_dependencies["mongo"].item_exists.return_value = False  # Items don't exist yet
    mock_dependencies["mongo"].get_items_by_status.return_value = pending_items
    mock_dependencies["mongo"].get_filtered_items.return_value = []

    # Make first 12 items high quality (>= 0.6 relevance)
    mock_dependencies["llm"].analyze_item.side_effect = [
        {"relevance_score": 0.8}
        if i < 12
        else {"relevance_score": 0.4, "filtered_reason": "low quality"}
        for i in range(15)
    ]

    # Run main function
    main()

    # Should have called update_feed once after first 10 high quality articles
    mock_update_feed.assert_called_once()

    # Should have called git_commit_and_push once after update_feed
    mock_git_commit.assert_called_once()

    # Verify items were stored during fetch phase (called once for each item)
    assert mock_dependencies["mongo"].store_feed_items.call_count == 15


def test_main_no_high_quality_articles(
    mock_dependencies,
    mock_update_feed,
    mock_git_commit,
    mock_feedly_session,
    setup_env_vars,
    test_items,
):
    # Setup test data
    items = test_items(5)
    mock_dependencies["fetcher"].get_stream_contents.return_value = {"items": items}

    # Mock MongoDB behavior for the new flow:
    # 1. First, item_exists returns False for all items (they don't exist yet)
    # 2. Then, get_items_by_status returns the items as pending for processing
    pending_items = [
        {**item, "category": "ML", "processing_status": "pending"} for item in items
    ]

    # Mock MongoDB methods properly for the 3-step flow
    mock_dependencies["mongo"].item_exists.return_value = False  # Items don't exist yet
    mock_dependencies["mongo"].get_items_by_status.return_value = pending_items
    mock_dependencies["mongo"].get_filtered_items.return_value = []

    # Make all items low quality (< 0.6 relevance)
    mock_dependencies["llm"].analyze_item.return_value = {
        "relevance_score": 0.4,
        "filtered_reason": "low quality",
    }

    # Run main function
    main()

    # Should not have called update_feed
    mock_update_feed.assert_not_called()

    # Should not have called git_commit_and_push
    mock_git_commit.assert_not_called()

    # Verify items were stored during fetch phase (called once for each item)
    assert mock_dependencies["mongo"].store_feed_items.call_count == 5


@responses.activate
def test_clean_item_data_with_url():
    """Test URL content fetching during item cleaning."""
    # Mock URL content
    test_url = "http://example.com/article"
    mock_html = """
    <html>
        <head>
            <title>Test Article</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <article>Test content</article>
        </body>
    </html>
    """
    responses.add(
        responses.GET, test_url, body=mock_html, status=200, content_type="text/html"
    )

    # Test item with URL
    item = {
        "alternate": [{"href": test_url}],
        "leoSummary": {"sentences": [{"text": "test"}]},
    }

    _clean_item_data(item)

    assert "url_content" in item
    assert item["url_content"]["title"] == "Test Article"
    assert item["url_content"]["description"] == "Test description"
    assert "Test content" in item["url_content"]["main_content"]
    assert item["leoSummary"]["sentences"] == ["test"]


@responses.activate
def test_clean_item_data_url_fetch_failure():
    """Test handling of URL fetch failures."""
    test_url = "http://example.com/error"
    responses.add(responses.GET, test_url, status=404)

    item = {
        "alternate": [{"href": test_url}],
        "leoSummary": {"sentences": [{"text": "test"}]},
    }

    _clean_item_data(item)

    assert "url_content" not in item
    assert item["leoSummary"]["sentences"] == ["test"]


def test_clean_item_data_no_url():
    """Test handling of items without URLs."""
    item = {"leoSummary": {"sentences": [{"text": "test"}]}}

    _clean_item_data(item)

    assert "url_content" not in item
    assert item["leoSummary"]["sentences"] == ["test"]


def test_main_unpublished_articles_trigger_feed_update(
    mock_dependencies,
    mock_update_feed,
    mock_git_commit,
    mock_feedly_session,
    setup_env_vars,
    test_items,
):
    """Test that unpublished high-quality articles trigger feed update in Step 3."""
    # Setup test data - only 3 items, not enough to trigger threshold during processing
    items = test_items(3)
    mock_dependencies["fetcher"].get_stream_contents.return_value = {"items": items}

    # Mock MongoDB behavior for the new flow:
    pending_items = [
        {**item, "category": "ML", "processing_status": "pending"} for item in items
    ]

    # Mock unpublished high-quality articles for Step 3
    unpublished_articles = [
        {
            "id": "unpublished_1",
            "title": "Unpublished Article 1",
            "category": "ML",
            "processing_status": "processed",
            "llm_analysis": {"relevance_score": 0.8},
            "published_to_feed": False,
        }
    ]

    # Mock MongoDB methods properly for the 3-step flow
    mock_dependencies["mongo"].item_exists.return_value = False  # Items don't exist yet
    mock_dependencies["mongo"].get_items_by_status.return_value = pending_items
    mock_dependencies["mongo"].get_filtered_items.return_value = unpublished_articles

    # Make all new items high quality but below threshold (3 < 10)
    mock_dependencies["llm"].analyze_item.return_value = {"relevance_score": 0.8}

    # Run main function
    main()

    # Should have called update_feed once in Step 3 for unpublished articles
    mock_update_feed.assert_called_once()

    # Should have called git_commit_and_push once after update_feed
    mock_git_commit.assert_called_once()

    # Verify items were stored during fetch phase
    assert mock_dependencies["mongo"].store_feed_items.call_count == 3
