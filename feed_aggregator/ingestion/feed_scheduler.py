import logging
from typing import Optional

from feed_aggregator.fetcher import FeedlyFetcher
from feed_aggregator.ingestion.data_normalizer import DataNormalizer
from feed_aggregator.storage.mongodb_client import MongoDBClient

logger = logging.getLogger(__name__)


class FeedScheduler:
    """Coordinates fetching and storing feed items."""

    def __init__(
        self,
        mongodb_client: Optional[MongoDBClient] = None,
        demo_mode: bool = False,
    ):
        """Initialize scheduler.

        Args:
            mongodb_client: Optional MongoDB client instance
            demo_mode: Whether to use demo data
        """
        self.mongodb = mongodb_client or MongoDBClient()
        self.fetcher = FeedlyFetcher(demo_mode=demo_mode)
        self.normalizer = DataNormalizer()

    def fetch_and_store(self, batch_size: int = 50) -> int:
        """Fetch items from sources and store in MongoDB.

        Args:
            batch_size: Number of items to fetch per source

        Returns:
            Number of items successfully stored
        """
        try:
            # Fetch items from Feedly
            response = self.fetcher.get_stream_contents(
                "user/-/category/global.all",
                count=batch_size,
            )

            if not response or "items" not in response:
                logger.warning("No items returned from Feedly")
                self.mongodb.record_metric(
                    "items_fetched",
                    0,
                    {"source": "feedly"},
                )
                return 0

            items = response["items"]
            if not items:
                logger.info("No new items to process")
                self.mongodb.record_metric(
                    "items_fetched",
                    0,
                    {"source": "feedly"},
                )
                return 0

            # Normalize items
            normalized_items = [
                self.normalizer.normalize(item, source="feedly") for item in items
            ]

            # Store items
            stored_count = self.mongodb.store_feed_items(normalized_items)

            # Record success metric
            self.mongodb.record_metric(
                "items_fetched",
                stored_count,
                {"source": "feedly"},
            )

            return stored_count

        except Exception as e:
            # Log error and record metric
            logger.error(f"Error fetching items: {str(e)}")
            self.mongodb.record_metric(
                "fetch_error",
                1,
                {"source": "feedly", "error": str(e)},
            )
            return 0

    def close(self) -> None:
        """Clean up resources."""
        if self.mongodb:
            self.mongodb.close()
