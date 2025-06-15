import logging
from datetime import UTC, datetime
from typing import Dict, List, Optional

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from feed_aggregator.config.mongodb_config import (
    EnvironmentMongoDBConfigProvider,
    MongoDBConfigProvider,
)

logger = logging.getLogger(__name__)


class MongoDBClient:
    """MongoDB client for feed storage and retrieval operations."""

    # Processing status constants
    STATUS_PENDING = "pending"
    STATUS_PROCESSED = "processed"
    STATUS_FILTERED = "filtered_out"
    STATUS_PUBLISHED = "published"

    def __init__(self, config_provider: Optional[MongoDBConfigProvider] = None):
        """Initialize MongoDB connection using configuration provider.

        Args:
            config_provider: MongoDB configuration provider. If None, uses environment variables.
        """
        if config_provider is None:
            config_provider = EnvironmentMongoDBConfigProvider()

        config = config_provider.get_config()
        uri = config.get_uri()

        # Initialize connection
        self.client = MongoClient(uri)
        self.db: Database = self.client[config.database]
        self.feed_items: Collection = self.db.feed_items
        self.metrics: Collection = self.db.processing_metrics

        logger.info(f"Connected to MongoDB at {config.host}:{config.port}")

    def store_feed_items(self, items: List[Dict]) -> int:
        """Store feed items in MongoDB.

        Args:
            items: List of feed items from Feedly API

        Returns:
            Number of items successfully stored
        """
        stored_count = 0
        for item in items:
            try:
                # Add processing status if not present
                if "processing_status" not in item:
                    item["processing_status"] = "pending"

                # Insert the item
                result = self.feed_items.update_one(
                    {"id": item["id"]},  # Use Feedly ID as unique identifier
                    {"$set": item},
                    upsert=True,
                )

                if result.upserted_id or result.modified_count:
                    stored_count += 1

            except DuplicateKeyError:
                logger.warning(f"Duplicate item found: {item.get('id')}")
            except Exception as e:
                logger.error(f"Error storing item {item.get('id')}: {str(e)}")

        # Record metric
        if stored_count > 0:
            self.record_metric("items_ingested", stored_count)

        return stored_count

    def get_items_by_status(
        self,
        status: str,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        sort_field: str = "published",
        sort_direction: int = ASCENDING,
    ) -> List[Dict]:
        """Get items by processing status with optional category filter.

        Args:
            status: Processing status to filter by
            category: Optional category to filter by
            limit: Optional maximum number of items to return
            sort_field: Field to sort by (default: published)
            sort_direction: Sort direction (default: ASCENDING)

        Returns:
            List of matching items
        """
        query = {"processing_status": status}
        if category:
            query["category"] = category

        cursor = self.feed_items.find(query)

        if sort_field:
            cursor = cursor.sort(sort_field, sort_direction)

        if limit:
            cursor = cursor.limit(limit)

        return list(cursor)

    def get_pending_items(self, limit: int = 100) -> List[Dict]:
        """Get items that need processing.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of items with pending status
        """
        return self.get_items_by_status(self.STATUS_PENDING, limit=limit)

    def item_exists(self, item_id: str) -> bool:
        """Check if an item exists in the database.

        Args:
            item_id: Feedly ID of the item

        Returns:
            True if item exists
        """
        return self.feed_items.count_documents({"id": item_id}) > 0

    def get_item(self, item_id: str) -> Optional[Dict]:
        """Get an item by its ID.

        Args:
            item_id: Feedly ID of the item

        Returns:
            Item document or None if not found
        """
        return self.feed_items.find_one({"id": item_id})

    def update_item(self, item_id: str, update_data: Dict) -> bool:
        """Update an item with the provided data.

        Args:
            item_id: Feedly ID of the item
            update_data: Dictionary of fields to update

        Returns:
            True if update was successful
        """
        result = self.feed_items.update_one({"id": item_id}, {"$set": update_data})
        return result.modified_count > 0

    def update_item_status(
        self, item_id: str, status: str, llm_analysis: Optional[Dict] = None
    ) -> bool:
        """Update an item's processing status and LLM analysis.

        Args:
            item_id: Feedly ID of the item
            status: New processing status
            llm_analysis: Optional LLM analysis results

        Returns:
            True if update was successful
        """
        update_data = {"processing_status": status}
        if llm_analysis:
            update_data["llm_analysis"] = llm_analysis

        # Mark as published if that's the new status
        if status == self.STATUS_PUBLISHED:
            update_data["published_to_feed"] = True

        return self.update_item(item_id, update_data)

    def get_filtered_items(
        self, min_score: float = 0.7, limit: int = 100, category: Optional[str] = None
    ) -> List[Dict]:
        """Get processed items that meet the relevance threshold and haven't been published.

        Args:
            min_score: Minimum relevance score (0-1)
            limit: Maximum number of items to return
            category: Optional category to filter by

        Returns:
            List of high-scoring items that haven't been published to feed
        """
        query = {
            "processing_status": {"$in": [self.STATUS_PROCESSED, self.STATUS_FILTERED]},
            "llm_analysis.relevance_score": {"$gte": min_score},
            "$or": [
                {"published_to_feed": {"$exists": False}},
                {"published_to_feed": False},
            ],
        }
        if category:
            query["category"] = category

        cursor = self.feed_items.find(query).sort("published", ASCENDING)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_status_counts(self) -> Dict[str, int]:
        """Get counts of items by processing status.

        Returns:
            Dictionary of status counts
        """
        return {
            "total": self.feed_items.count_documents({}),
            "pending": self.feed_items.count_documents(
                {"processing_status": self.STATUS_PENDING}
            ),
            "processed": self.feed_items.count_documents(
                {"processing_status": self.STATUS_PROCESSED}
            ),
            "filtered": self.feed_items.count_documents(
                {"processing_status": self.STATUS_FILTERED}
            ),
            "published": self.feed_items.count_documents(
                {"processing_status": self.STATUS_PUBLISHED}
            ),
        }

    def record_metric(
        self, metric_type: str, value: float, metadata: Optional[Dict] = None
    ) -> None:
        """Record a processing metric.

        Args:
            metric_type: Type of metric
            value: Metric value
            metadata: Optional additional context
        """
        metric = {
            "timestamp": datetime.now(UTC),
            "metric_type": metric_type,
            "value": value,
        }
        if metadata:
            metric["metadata"] = metadata

        try:
            self.metrics.insert_one(metric)
        except Exception as e:
            logger.error(f"Error recording metric: {str(e)}")

    def close(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")
