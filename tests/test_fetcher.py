import unittest
from unittest.mock import patch, Mock
from feed_aggregator.fetcher import FeedlyFetcher


class TestFeedlyFetcher(unittest.TestCase):
    @patch('feedly.api_client.client.request.urlopen')
    def test_get_stream_contents(self, mock_urlopen):
        mock_resp = Mock()
        mock_resp.read.return_value = b'{"items": [{"title": "test"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        fetcher = FeedlyFetcher(token="token")
        result = fetcher.get_stream_contents("stream")
        self.assertEqual(result["items"][0]["title"], "test")
        mock_urlopen.assert_called_once()
