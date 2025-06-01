import os
from feedly.api_client import FeedlyClient


class FeedlyFetcher:
    """Wrapper around feedly/python-api-client's FeedlyClient."""

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("FEEDLY_TOKEN")
        if not self.token:
            raise ValueError("FEEDLY_TOKEN environment variable not set")
        self.client = FeedlyClient(self.token)

    def get_stream_contents(self, stream_id: str, count: int = 10) -> dict:
        """Return contents for a given stream id."""
        return self.client.get_stream_contents(stream_id, count=count)
