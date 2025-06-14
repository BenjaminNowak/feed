#!/usr/bin/env python3
import argparse
from datetime import datetime

from feed_aggregator.storage.mongodb_client import MongoDBClient


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="List recently ingested feed items")
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=5,
        help="Number of recent items to show (default: 5)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full item details instead of summary",
    )
    return parser.parse_args()


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp to readable date."""
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")


def print_item_summary(item: dict) -> None:
    """Print a summary of a feed item."""
    print(f"\nTitle: {item.get('title', 'No title')}")
    print(f"Source: {item.get('origin', {}).get('title', 'Unknown source')}")
    print(f"URL: {item.get('originId', 'No URL')}")
    print(f"Published: {format_timestamp(item.get('published', 0))}")
    print(f"Crawled: {format_timestamp(item.get('crawled', 0))}")
    print(f"Status: {item.get('processing_status', 'unknown')}")

    # Print topics if available
    if "commonTopics" in item:
        topics = [t["label"] for t in item["commonTopics"]]
        print(f"Topics: {', '.join(topics)}")

    # Print categories if available
    if "categories" in item:
        categories = [c["label"] for c in item["categories"]]
        print(f"Categories: {', '.join(categories)}")


def main():
    args = parse_args()

    # Initialize MongoDB client
    mongo_client = MongoDBClient()

    try:
        # Get recent items sorted by crawl time
        recent_items = list(
            mongo_client.feed_items.find().sort("crawled", -1).limit(args.count)
        )

        if not recent_items:
            print("No items found in MongoDB")
            return

        print(f"\nMost recent {len(recent_items)} items:")

        for item in recent_items:
            if args.full:
                # Print full item details
                print("\n" + "=" * 80)
                for key, value in item.items():
                    if key != "_id":  # Skip MongoDB ID
                        print(f"{key}: {value}")
            else:
                # Print summary
                print_item_summary(item)

    finally:
        # Close MongoDB connection
        mongo_client.close()


if __name__ == "__main__":
    main()
