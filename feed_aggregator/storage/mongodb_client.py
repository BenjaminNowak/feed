import logging
import os
from datetime import UTC, datetime
from typing import Dict, List, Optional

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


class MongoDBClient:
    """MongoDB client for feed storage."""

    def __init__(self):
        """Initialize MongoDB connection using environment variables."""
        # Get MongoDB connection details from environment
        host = os.getenv("MONGODB_HOST", "localhost")
        port = int(os.getenv("MONGODB_PORT", "27017"))
        username = os.getenv("MONGODB_USERNAME", "feeduser")
        password = os.getenv("MONGODB_PASSWORD", "")
        database = os.getenv("MONGODB_DATABASE", "feeddb")

        # Construct MongoDB URI
        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        # Initialize connection
        self.client = MongoClient(uri)
        self.db: Database = self.client[database]
        self.feed_items: Collection = self.db.feed_items
        self.metrics: Collection = self.db.processing_metrics

        logger.info(f"Connected to MongoDB at {host}:{port}")

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

    def get_pending_items(self, limit: int = 100) -> List[Dict]:
        """Get items that need processing.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of items with pending status
        """
        return list(
            self.feed_items.find({"processing_status": "pending"}, limit=limit).sort(
                "published", ASCENDING
            )
        )

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

        result = self.feed_items.update_one({"id": item_id}, {"$set": update_data})

        return result.modified_count > 0

    def get_filtered_items(
        self, min_score: float = 0.7, limit: int = 100
    ) -> List[Dict]:
        """Get processed items that meet the relevance threshold.

        Args:
            min_score: Minimum relevance score (0-1)
            limit: Maximum number of items to return

        Returns:
            List of high-scoring items
        """
        return list(
            self.feed_items.find(
                {
                    "processing_status": "processed",
                    "llm_analysis.relevance_score": {"$gte": min_score},
                },
                limit=limit,
            ).sort("published", ASCENDING)
        )

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
