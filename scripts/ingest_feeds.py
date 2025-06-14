#!/usr/bin/env python3
import argparse
import os
from typing import Dict, List

from feed_aggregator.fetcher import FeedlyFetcher
from feed_aggregator.storage.mongodb_client import MongoDBClient


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Ingest feeds from Feedly to MongoDB")
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of items to fetch (default: 100)",
    )
    parser.add_argument(
        "--stream-id",
        type=str,
        help="Feedly stream ID to fetch from (default: user's global.all category)",
    )
    return parser.parse_args()


def get_existing_ids(mongo_client: MongoDBClient) -> set:
    """Get set of existing feed item IDs from MongoDB."""
    return {doc["id"] for doc in mongo_client.feed_items.find({}, {"id": 1})}


def normalize_item(item: Dict) -> Dict:
    """Normalize item data to match MongoDB schema."""
    # Deep copy to avoid modifying original
    normalized = item.copy()

    # Set default processing status
    normalized["processing_status"] = "pending"

    # Handle leoSummary sentences
    if "leoSummary" in normalized:
        if "sentences" in normalized["leoSummary"]:
            sentences = normalized["leoSummary"]["sentences"]
            # Convert sentence objects to strings
            normalized["leoSummary"]["sentences"] = [
                s["text"] if isinstance(s, dict) else s for s in sentences
            ]

    # Ensure required fields exist
    required_fields = ["fingerprint", "id", "title", "crawled"]
    for field in required_fields:
        if field not in normalized:
            if field == "fingerprint":
                normalized["fingerprint"] = normalized.get("id", "")
            else:
                normalized[field] = ""

    return normalized


def store_new_items(
    mongo_client: MongoDBClient, items: List[Dict], existing_ids: set
) -> Dict[str, int]:
    """Store new items in MongoDB and return stats."""
    stats = {"new": 0, "skipped": 0, "error": 0}

    for item in items:
        try:
            if item["id"] in existing_ids:
                stats["skipped"] += 1
                continue

            # Normalize item data
            normalized = normalize_item(item)

            # Store new item
            mongo_client.feed_items.insert_one(normalized)
            stats["new"] += 1

        except Exception as e:
            print(f"Error storing item: {str(e)}")
            stats["error"] += 1
            continue

    return stats


def print_summary(stats: Dict[str, int], metrics: Dict[str, int]) -> None:
    """Print ingestion summary."""
    print("\nIngestion Summary:")
    print(f"New items added: {stats['new']}")
    print(f"Duplicate items skipped: {stats['skipped']}")
    print(f"Items with errors: {stats['error']}")

    print("\nMongoDB Status:")
    print(f"Total items: {metrics['total_items']}")
    print(f"Pending items: {metrics['pending_items']}")
    print(f"Processed items: {metrics['processed_items']}")
    print(f"Filtered items: {metrics['filtered_items']}")
    print(f"Published items: {metrics['published_items']}")


def main():
    args = parse_args()

    # Check if we have a Feedly token and user ID, otherwise use demo mode
    token = os.environ.get("FEEDLY_TOKEN")
    user_id = os.environ.get("FEEDLY_USER")

    # Use provided stream ID or default
    stream_id = args.stream_id or os.environ.get(
        "FEEDLY_STREAM_ID",
        f"user/{user_id}/category/global.all"
        if user_id
        else "user/808d013f-58fe-49e9-890e-53d4a5157874/category/global.all",
    )

    if token:
        print("Using Feedly API with provided token...")
        if user_id:
            print(f"Using user ID: {user_id}")
        fetcher = FeedlyFetcher(token=token, user_id=user_id)
    else:
        print("No FEEDLY_TOKEN found, using demo mode...")
        fetcher = FeedlyFetcher(demo_mode=True)

    # Initialize MongoDB client
    mongo_client = MongoDBClient()

    try:
        # Get existing item IDs
        existing_ids = get_existing_ids(mongo_client)
        print(f"\nFound {len(existing_ids)} existing items in MongoDB")

        # Fetch data from Feedly
        data = fetcher.get_stream_contents(stream_id, count=args.count)
        print(f"Fetched {len(data['items'])} items from Feedly")

        # Store new items and track stats
        stats = store_new_items(mongo_client, data["items"], existing_ids)

        # Get metrics
        metrics = {
            "total_items": mongo_client.feed_items.count_documents({}),
            "pending_items": mongo_client.feed_items.count_documents(
                {"processing_status": "pending"}
            ),
            "processed_items": mongo_client.feed_items.count_documents(
                {"processing_status": "processed"}
            ),
            "filtered_items": mongo_client.feed_items.count_documents(
                {"processing_status": "filtered_out"}
            ),
            "published_items": mongo_client.feed_items.count_documents(
                {"processing_status": "published"}
            ),
        }

        print_summary(stats, metrics)

    finally:
        # Close MongoDB connection
        mongo_client.close()


if __name__ == "__main__":
    main()
