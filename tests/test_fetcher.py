import unittest
from unittest.mock import MagicMock, patch

from feed_aggregator.fetcher import FeedlyFetcher


class TestFeedlyFetcher(unittest.TestCase):
    def test_get_stream_contents_uses_first_available_category(
        self,
    ):
        """Test that global.all stream uses first available category."""
        # Create mock objects
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_categories = MagicMock()

        # Setup the mock chain
        mock_session.user = mock_user
        mock_user.user_categories = mock_categories
        mock_categories.name2stream = {"Culture": None, "Tech": None}

        # Setup mock category and stream
        mock_category = MagicMock()
        mock_category.stream_contents.return_value = []
        mock_categories.get.return_value = mock_category

        # Create fetcher and inject our mock session
        fetcher = FeedlyFetcher(token="test-token", user_id="test-user")
        fetcher.session = mock_session

        # Test with global.all stream ID
        stream_id = "user/test-user/category/global.all"
        fetcher.get_stream_contents(stream_id)

        # Verify that get() was called with the first available category
        mock_categories.get.assert_called_once_with("Culture")

    def test_get_stream_contents_demo_mode(self):
        """Test that demo mode returns sample data."""
        fetcher = FeedlyFetcher(demo_mode=True)
        result = fetcher.get_stream_contents("user/-/category/global.all", count=1)

        self.assertIn("items", result)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(
            result["items"][0]["title"],
            "AlphaEvolve: A Gemini-Powered Coding Agent "
            "for Designing Advanced Algorithms",
        )
        self.assertEqual(result["id"], "user/-/category/global.all")

    def test_demo_mode_respects_count(self):
        """Test that demo mode respects the count parameter."""
        fetcher = FeedlyFetcher(demo_mode=True)
        result = fetcher.get_stream_contents("test-stream", count=2)

        self.assertEqual(len(result["items"]), 2)

    @patch.dict("os.environ", {}, clear=True)
    def test_requires_token_without_demo_mode(self):
        """Test that FeedlyFetcher requires a token when not in demo mode."""
        with self.assertRaises(ValueError) as context:
            FeedlyFetcher(demo_mode=False)

        self.assertIn("FEEDLY_TOKEN", str(context.exception))
