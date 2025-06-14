import os

from feed_aggregator.fetcher import FeedlyFetcher
from feed_aggregator.storage.mongodb_client import MongoDBClient


def main():
    # Check if we have a Feedly token and user ID, otherwise use demo mode
    token = os.environ.get("FEEDLY_TOKEN")
    user_id = os.environ.get("FEEDLY_USER")

    # Use FEEDLY_STREAM_ID environment variable or a default
    stream_id = os.environ.get(
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
        # Fetch data from Feedly
        data = fetcher.get_stream_contents(stream_id, count=1)
        print(f"\nFetched {len(data['items'])} items from Feedly")

        # Store items in MongoDB
        stored_count = mongo_client.store_feed_items(data["items"])
        print(f"Stored {stored_count} items in MongoDB")

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

        print("\nCurrent MongoDB Status:")
        print(f"Total items: {metrics['total_items']}")
        print(f"Pending items: {metrics['pending_items']}")
        print(f"Processed items: {metrics['processed_items']}")
        print(f"Filtered items: {metrics['filtered_items']}")
        print(f"Published items: {metrics['published_items']}")

    finally:
        # Close MongoDB connection
        mongo_client.close()


if __name__ == "__main__":
    main()
