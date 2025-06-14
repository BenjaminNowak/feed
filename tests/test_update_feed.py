import os
import tempfile
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

import pytest

from feed_aggregator.etl.update_feed import add_item, format_datetime, load_feed, main


@pytest.fixture
def sample_article():
    """Sample article data for testing."""
    return {
        "id": "test_article_123",
        "title": "Test Article Title",
        "content": {"content": "This is test content with <p>HTML tags</p>"},
        "summary": {"content": "Test summary"},
        "alternate": [{"type": "text/html", "href": "https://example.com/article"}],
        "published": 1733097600000,  # 2024-12-02 00:00:00 UTC
        "author": "Test Author",
    }


@pytest.fixture
def sample_article_with_leo_summary():
    """Sample article with leoSummary for testing."""
    return {
        "id": "test_article_456",
        "title": "Test Article with Leo Summary",
        "content": {"content": "Test content"},
        "leoSummary": {
            "sentences": [
                {"text": "First sentence"},
                {"text": "Second sentence"},
                "Third sentence as string",
            ]
        },
        "alternate": [{"type": "text/html", "href": "https://example.com/article2"}],
        "published": 1733097600000,
    }


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB client."""
    with patch("feed_aggregator.etl.update_feed.MongoDBClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_filtered_items.return_value = []
        mock_instance.update_item_status = MagicMock()
        mock_instance.close = MagicMock()
        yield mock_instance


class TestFormatDatetime:
    """Tests for format_datetime function."""

    def test_format_datetime_milliseconds(self):
        """Test formatting millisecond timestamp."""
        # 2024-12-02 00:00:00 UTC
        timestamp_ms = 1733097600000
        result = format_datetime(timestamp_ms)
        assert result == "Mon, 02 Dec 2024 00:00:00 +0000"

    def test_format_datetime_different_time(self):
        """Test formatting different timestamp."""
        # 2024-06-14 16:30:00 UTC
        timestamp_ms = 1718382600000
        result = format_datetime(timestamp_ms)
        assert result == "Fri, 14 Jun 2024 16:30:00 +0000"


class TestLoadFeed:
    """Tests for load_feed function."""

    def test_load_feed_creates_new_feed(self):
        """Test creating new feed when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                root, channel = load_feed()

                # Check root element
                assert root.tag == "rss"
                assert root.get("version") == "2.0"

                # Check channel elements
                assert channel.find("title").text == "AI and Tech Feed"
                expected_desc = (
                    "Curated articles about artificial intelligence, technology, "
                    "and software development, filtered by relevance and technical value"
                )
                assert channel.find("description").text == expected_desc
                assert (
                    channel.find("link").text == "https://github.com/BenjaminNowak/feed"
                )

            finally:
                os.chdir(original_cwd)

    def test_load_feed_updates_existing_feed(self):
        """Test updating existing feed file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create existing feed file
                existing_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Old Title</title>
    <description>Old Description</description>
    <link>https://old-link.com</link>
    <item>
      <title>Existing Item</title>
      <guid>existing_123</guid>
    </item>
  </channel>
</rss>"""
                with open("feed.xml", "w") as f:
                    f.write(existing_feed)

                root, channel = load_feed()

                # Check that metadata was updated
                assert channel.find("title").text == "AI and Tech Feed"
                expected_desc = (
                    "Curated articles about artificial intelligence, technology, "
                    "and software development, filtered by relevance and technical value"
                )
                assert channel.find("description").text == expected_desc
                assert (
                    channel.find("link").text == "https://github.com/BenjaminNowak/feed"
                )

                # Check that existing item is preserved
                items = channel.findall("item")
                assert len(items) == 1
                assert items[0].find("title").text == "Existing Item"

            finally:
                os.chdir(original_cwd)


class TestAddItem:
    """Tests for add_item function."""

    def test_add_item_new_article(self, sample_article):
        """Test adding new article to feed."""
        root = ET.Element("rss")
        channel = ET.SubElement(root, "channel")

        result = add_item(channel, sample_article)

        assert result is True
        items = channel.findall("item")
        assert len(items) == 1

        item = items[0]
        assert item.find("title").text == "Test Article Title"
        assert item.find("guid").text == "test_article_123"
        assert item.find("link").text == "https://example.com/article"
        assert "This is test content" in item.find("description").text

    def test_add_item_duplicate_article(self, sample_article):
        """Test adding duplicate article (should be skipped)."""
        root = ET.Element("rss")
        channel = ET.SubElement(root, "channel")

        # Add item first time
        add_item(channel, sample_article)
        assert len(channel.findall("item")) == 1

        # Try to add same item again
        result = add_item(channel, sample_article)
        assert result is False
        assert len(channel.findall("item")) == 1  # Should still be 1

    def test_add_item_content_cleaning(self):
        """Test HTML content cleaning in add_item."""
        article = {
            "id": "test_clean",
            "title": "Test Cleaning",
            "content": {
                "content": "<p>Clean content</p><div>Remove this</div><br>Keep breaks"
            },
            "alternate": [{"type": "text/html", "href": "https://example.com"}],
            "published": 1733097600000,
        }

        root = ET.Element("rss")
        channel = ET.SubElement(root, "channel")
        add_item(channel, article)

        item = channel.find("item")
        description = item.find("description").text
        # Should clean HTML but preserve basic structure
        assert "<div>" not in description
        assert "Clean content" in description

    def test_add_item_with_summary_fallback(self):
        """Test using summary when content is not available."""
        article = {
            "id": "test_summary",
            "title": "Test Summary",
            "summary": {"content": "This is summary content"},
            "alternate": [{"type": "text/html", "href": "https://example.com"}],
            "published": 1733097600000,
        }

        root = ET.Element("rss")
        channel = ET.SubElement(root, "channel")
        add_item(channel, article)

        item = channel.find("item")
        description = item.find("description").text
        assert "This is summary content" in description


class TestMain:
    """Tests for main function."""

    def test_main_no_articles(self, mock_mongo_client):
        """Test main function with no articles to process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                mock_mongo_client.get_filtered_items.return_value = []

                main()

                # Should create feed.xml even with no articles
                assert os.path.exists("feed.xml")

                # Verify MongoDB methods were called
                mock_mongo_client.get_filtered_items.assert_called_once_with(
                    min_score=0.6
                )
                mock_mongo_client.close.assert_called_once()

            finally:
                os.chdir(original_cwd)

    def test_main_with_articles(self, mock_mongo_client, sample_article):
        """Test main function with articles to process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                mock_mongo_client.get_filtered_items.return_value = [sample_article]

                main()

                # Verify feed.xml was created
                assert os.path.exists("feed.xml")

                # Parse and verify content
                tree = ET.parse("feed.xml")
                root = tree.getroot()
                items = root.findall(".//item")
                assert len(items) == 1
                assert items[0].find("title").text == "Test Article Title"

                # Verify MongoDB methods were called
                mock_mongo_client.update_item_status.assert_called_once_with(
                    "test_article_123", "published"
                )

            finally:
                os.chdir(original_cwd)

    def test_main_with_duplicate_articles(self, mock_mongo_client, sample_article):
        """Test main function handles duplicate articles correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create existing feed with the article
                existing_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AI and Tech Feed</title>
    <description>Test</description>
    <link>https://github.com/BenjaminNowak/feed</link>
    <item>
      <title>Test Article Title</title>
      <guid>{sample_article['id']}</guid>
    </item>
  </channel>
</rss>"""
                with open("feed.xml", "w") as f:
                    f.write(existing_feed)

                mock_mongo_client.get_filtered_items.return_value = [sample_article]

                main()

                # Parse and verify only one item exists (duplicate was skipped)
                tree = ET.parse("feed.xml")
                root = tree.getroot()
                items = root.findall(".//item")
                assert len(items) == 1

                # update_item_status should not be called for duplicates
                mock_mongo_client.update_item_status.assert_not_called()

            finally:
                os.chdir(original_cwd)

    def test_main_cleans_existing_items(self, mock_mongo_client):
        """Test that main function cleans existing items in feed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)

                # Create feed with item that needs cleaning
                existing_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AI and Tech Feed</title>
    <description>Test</description>
    <link>https://github.com/BenjaminNowak/feed</link>
    <item>
      <title>Test</title>
      <description><![CDATA[Content with <div>HTML</div> and params?utm_source=test]]></description>
      <link>https://example.com/article?utm_source=test&amp;utm_medium=rss</link>
      <guid>test_123</guid>
    </item>
  </channel>
</rss>"""
                with open("feed.xml", "w") as f:
                    f.write(existing_feed)

                mock_mongo_client.get_filtered_items.return_value = []

                main()

                # Parse and verify content was cleaned
                tree = ET.parse("feed.xml")
                root = tree.getroot()
                item = root.find(".//item")

                # Link should be cleaned (remove query params)
                link = item.find("link").text
                assert "?" not in link
                assert link == "https://example.com/article"

            finally:
                os.chdir(original_cwd)
