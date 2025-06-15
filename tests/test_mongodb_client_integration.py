"""Integration tests for MongoDB client using testcontainers."""
import time
from datetime import UTC, datetime
from typing import Generator

import pytest
from pymongo import ASCENDING
from pymongo.operations import UpdateOne
from testcontainers.mongodb import MongoDbContainer

from feed_aggregator.storage.mongodb_client import MongoDBClient


def wait_for_mongodb(client, timeout=30, interval=1):
    """Wait for MongoDB to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Ping the database
            client.admin.command("ping")
            return True
        except Exception:
            time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def mongodb_container() -> Generator[MongoDbContainer, None, None]:
    """Create a MongoDB test container that persists for the entire test session."""
    # Use MongoDbContainer with no authentication (username=None, password=None)
    container = MongoDbContainer(
        image="mongo:7",
        username=None,  # No authentication
        password=None,  # No authentication
        dbname="test_db",
    )

    with container:
        print(
            f"MongoDB test container running on {container.get_container_host_ip()}:{container.get_exposed_port(27017)}"
        )
        # Wait for container to be ready
        client = container.get_connection_client()
        if not wait_for_mongodb(client):
            raise Exception("MongoDB container failed to become ready")
        client.close()
        yield container


@pytest.fixture
def mongodb_client(mongodb_container) -> Generator[MongoDBClient, None, None]:
    """Create a MongoDB client connected to the test container."""
    # Use the container's built-in connection method which handles auth properly
    pymongo_client = mongodb_container.get_connection_client()

    # Create a custom MongoDBClient that uses the pre-configured pymongo client
    class TestMongoDBClient(MongoDBClient):
        def __init__(self, pymongo_client, database_name="test_db"):
            # Skip the normal __init__ and set up manually
            self.client = pymongo_client
            self.db = self.client[database_name]
            self.feed_items = self.db.feed_items
            self.metrics = self.db.processing_metrics

    client = TestMongoDBClient(pymongo_client)
    yield client
    # Cleanup after each test
    client.feed_items.delete_many({})
    client.metrics.delete_many({})
    client.close()


@pytest.fixture
def sample_feed_items():
    """Create sample feed items for testing."""
    current_time = int(datetime.now(UTC).timestamp() * 1000)
    return [
        {
            "id": "test_1",
            "title": "Test Article 1",
            "content": {"content": "Test content 1"},
            "published": current_time - 3600000,  # 1 hour ago
            "processing_status": "pending",
        },
        {
            "id": "test_2",
            "title": "Test Article 2",
            "content": {"content": "Test content 2"},
            "published": current_time - 7200000,  # 2 hours ago
            "processing_status": "pending",
        },
    ]


@pytest.mark.integration
class TestMongoDBClientIntegration:
    """Integration tests for MongoDBClient using a real MongoDB instance."""

    def test_store_and_retrieve_feed_items(self, mongodb_client, sample_feed_items):
        """Test storing and retrieving feed items in MongoDB."""
        # Store items
        stored_count = mongodb_client.store_feed_items(sample_feed_items)
        assert stored_count == 2

        # Verify items were stored
        for item in sample_feed_items:
            stored_item = mongodb_client.get_item(item["id"])
            assert stored_item is not None
            assert stored_item["title"] == item["title"]
            assert stored_item["content"]["content"] == item["content"]["content"]

    def test_update_item_status_with_llm_analysis(
        self, mongodb_client, sample_feed_items
    ):
        """Test updating item status with LLM analysis."""
        # Store test item
        mongodb_client.store_feed_items([sample_feed_items[0]])

        # Update status with LLM analysis
        llm_analysis = {
            "relevance_score": 0.8,
            "summary": "Test summary",
            "keywords": ["test", "article"],
        }
        success = mongodb_client.update_item_status(
            sample_feed_items[0]["id"], mongodb_client.STATUS_PROCESSED, llm_analysis
        )
        assert success is True

        # Verify update
        updated_item = mongodb_client.get_item(sample_feed_items[0]["id"])
        assert updated_item["processing_status"] == mongodb_client.STATUS_PROCESSED
        assert updated_item["llm_analysis"] == llm_analysis

    def test_get_filtered_items_with_scoring(self, mongodb_client):
        """Test retrieving filtered items with relevance scoring."""
        # Store test items with different scores
        items = [
            {
                "id": "high_1",
                "title": "High Score 1",
                "processing_status": "processed",
                "llm_analysis": {"relevance_score": 0.9},
                "published_to_feed": False,
            },
            {
                "id": "high_2",
                "title": "High Score 2",
                "processing_status": "processed",
                "llm_analysis": {"relevance_score": 0.8},
                "published_to_feed": False,
            },
            {
                "id": "low_1",
                "title": "Low Score",
                "processing_status": "processed",
                "llm_analysis": {"relevance_score": 0.5},
                "published_to_feed": False,
            },
        ]
        mongodb_client.store_feed_items(items)

        # Get filtered items with high scores
        filtered_items = mongodb_client.get_filtered_items(min_score=0.7)
        assert len(filtered_items) == 2
        assert all(
            item["llm_analysis"]["relevance_score"] >= 0.7 for item in filtered_items
        )

        # Get filtered items with lower threshold
        all_items = mongodb_client.get_filtered_items(min_score=0.4)
        assert len(all_items) == 3

    def test_record_and_query_metrics(self, mongodb_client):
        """Test recording and querying processing metrics."""
        # Record multiple metrics
        metrics_data = [
            ("items_processed", 5, {"source": "test1"}),
            ("items_filtered", 2, {"source": "test1"}),
            ("items_processed", 3, {"source": "test2"}),
        ]

        for metric_type, value, metadata in metrics_data:
            mongodb_client.record_metric(metric_type, value, metadata)

        # Query metrics
        all_metrics = list(mongodb_client.metrics.find({}))
        assert len(all_metrics) == 3

        # Query specific metric type
        processed_metrics = list(
            mongodb_client.metrics.find({"metric_type": "items_processed"})
        )
        assert len(processed_metrics) == 2
        assert sum(m["value"] for m in processed_metrics) == 8

    def test_concurrent_operations(self, mongodb_client, sample_feed_items):
        """Test handling of concurrent operations."""
        # Store initial items
        mongodb_client.store_feed_items(sample_feed_items)

        # Update items concurrently (simulated)
        for item in sample_feed_items:
            # Update status
            mongodb_client.update_item_status(
                item["id"], mongodb_client.STATUS_PROCESSED, {"relevance_score": 0.75}
            )
            # Record metric
            mongodb_client.record_metric("item_processed", 1, {"item_id": item["id"]})

        # Verify all operations completed
        processed_items = list(
            mongodb_client.feed_items.find(
                {"processing_status": mongodb_client.STATUS_PROCESSED}
            )
        )
        assert len(processed_items) == 2

        metrics = list(mongodb_client.metrics.find({"metric_type": "item_processed"}))
        assert len(metrics) == 2

    def test_error_handling(self, mongodb_client):
        """Test error handling with invalid operations."""
        # Test duplicate key handling
        item = {
            "id": "duplicate_test",
            "title": "Duplicate Test",
            "processing_status": "pending",
        }

        # First insertion should succeed
        assert mongodb_client.store_feed_items([item]) == 1

        # Second insertion of same ID should be handled gracefully
        assert mongodb_client.store_feed_items([item]) == 0

        # Test invalid update
        assert mongodb_client.update_item("nonexistent_id", {"status": "test"}) is False

    def test_complex_aggregation_metrics(self, mongodb_client):
        """Test complex aggregation pipeline for advanced metrics."""
        # Insert test data with various statuses and categories
        test_items = [
            {
                "id": f"test_{i}",
                "title": f"Test {i}",
                "category": "tech" if i % 2 == 0 else "cyber",
                "processing_status": mongodb_client.STATUS_PROCESSED
                if i % 3 == 0
                else mongodb_client.STATUS_FILTERED
                if i % 3 == 1
                else mongodb_client.STATUS_PENDING,
                "llm_analysis": {"relevance_score": 0.5 + (i / 10)},
                "published": datetime.now(UTC).timestamp() * 1000,
            }
            for i in range(10)
        ]
        mongodb_client.store_feed_items(test_items)

        # Get status counts by category using aggregation
        pipeline = [
            {
                "$group": {
                    "_id": {"category": "$category", "status": "$processing_status"},
                    "count": {"$sum": 1},
                    "avg_score": {"$avg": "$llm_analysis.relevance_score"},
                }
            },
            {"$sort": {"_id.category": 1, "_id.status": 1}},
        ]

        results = list(mongodb_client.feed_items.aggregate(pipeline))
        assert len(results) > 0

        # Verify aggregation results
        for result in results:
            assert "count" in result
            assert "avg_score" in result
            assert "_id" in result and "category" in result["_id"]

    def test_index_performance(self, mongodb_client):
        """Test index usage and performance."""
        # Create compound index
        mongodb_client.feed_items.create_index(
            [
                ("category", ASCENDING),
                ("processing_status", ASCENDING),
                ("published", ASCENDING),
            ],
            name="category_status_published_idx",
        )

        # Insert test data
        test_items = [
            {
                "id": f"perf_test_{i}",
                "title": f"Performance Test {i}",
                "category": "tech",
                "processing_status": mongodb_client.STATUS_PROCESSED,
                "published": datetime.now(UTC).timestamp() * 1000 - (i * 1000),
                "llm_analysis": {"relevance_score": 0.8},
            }
            for i in range(100)
        ]
        mongodb_client.store_feed_items(test_items)

        # Query using index
        query = {
            "category": "tech",
            "processing_status": mongodb_client.STATUS_PROCESSED,
        }

        # Get query explanation
        explanation = mongodb_client.feed_items.find(query).explain()

        # Verify index usage
        assert "queryPlanner" in explanation
        assert "winningPlan" in explanation["queryPlanner"]
        assert "inputStage" in explanation["queryPlanner"]["winningPlan"]

        # Verify query uses index
        winning_plan = explanation["queryPlanner"]["winningPlan"]
        assert "indexName" in winning_plan["inputStage"]
        assert (
            winning_plan["inputStage"]["indexName"] == "category_status_published_idx"
        )

    def test_bulk_operations(self, mongodb_client):
        """Test bulk operations with large datasets."""
        # Create large dataset
        bulk_items = [
            {
                "id": f"bulk_test_{i}",
                "title": f"Bulk Test {i}",
                "content": {"content": f"Bulk content {i}"},
                "processing_status": "pending",
                "published": datetime.now(UTC).timestamp() * 1000 - (i * 1000),
            }
            for i in range(1000)
        ]

        # Test bulk insert
        stored_count = mongodb_client.store_feed_items(bulk_items)
        assert stored_count == 1000

        # Test bulk update
        bulk_ops = []
        for i in range(1000):
            bulk_ops.append(
                UpdateOne(
                    {"id": f"bulk_test_{i}"},
                    {"$set": {"processing_status": "processed"}},
                )
            )
        result = mongodb_client.feed_items.bulk_write(bulk_ops)
        assert result.modified_count == 1000

        # Verify updates
        processed_count = mongodb_client.feed_items.count_documents(
            {"processing_status": "processed"}
        )
        assert processed_count == 1000
