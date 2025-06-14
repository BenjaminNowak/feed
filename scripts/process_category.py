import os

from feed_aggregator.fetcher import FeedlyFetcher
from feed_aggregator.processing.content_analyzer import ContentAnalyzer
from feed_aggregator.processing.llm_filter import LLMFilter
from feed_aggregator.storage.mongodb_client import MongoDBClient


def main():
    # Initialize fetcher
    token = os.environ.get("FEEDLY_TOKEN")
    user_id = os.environ.get("FEEDLY_USER")

    if not token:
        raise ValueError("FEEDLY_TOKEN environment variable not set")

    fetcher = FeedlyFetcher(token=token, user_id=user_id)

    # Initialize analyzers
    content_analyzer = ContentAnalyzer()
    llm_filter = LLMFilter(provider="ollama")
    mongo_client = MongoDBClient()

    try:
        # Get all categories
        available_categories = list(
            fetcher.session.user.user_categories.name2stream.keys()
        )
        print(f"Available categories: {available_categories}")

        # Find Machine Learning category
        ml_category = "Culture"  # Exact match with trailing space
        if ml_category not in available_categories:
            raise ValueError("Machine Learning category not found")

        print(f"\nFetching from category: {ml_category}")

        # Get stream contents
        data = fetcher.get_stream_contents(
            f"user/{user_id}/category/{ml_category}", count=100
        )

        print(f"\nFetched {len(data['items'])} items")

        # Process each item
        for i, item in enumerate(data["items"], 1):
            print(f"\nProcessing item {i}/{len(data['items'])}")
            print(f"Title: {item.get('title', 'No title')}")

            try:
                # Check if item exists and has been analyzed
                existing_item = mongo_client.feed_items.find_one({"id": item["id"]})
                if existing_item and "llm_analysis" in existing_item:
                    print("Item already analyzed, skipping...")
                    continue

                # Run content analysis
                content = item.get("content", {}).get(
                    "content", item.get("summary", {}).get("content", "")
                )

                content_analysis = content_analyzer.analyze_item(
                    {"content": content, "llm_analysis": {}}
                )

                # Run LLM analysis
                llm_analysis = llm_filter.analyze_item(
                    {"title": item.get("title", ""), "content": content}
                )

                # Add analyses to item
                item["content_analysis"] = content_analysis
                item["llm_analysis"] = llm_analysis
                item["processing_status"] = "processed"

                # Print analysis results
                print(f"Relevance score: {llm_analysis['relevance_score']}")
                if llm_analysis.get("filtered_reason"):
                    print(f"Filtered reason: {llm_analysis['filtered_reason']}")
                    item["processing_status"] = "filtered_out"

                # Clean up leoSummary if present
                if "leoSummary" in item and "sentences" in item["leoSummary"]:
                    # Convert sentence objects to strings
                    item["leoSummary"]["sentences"] = [
                        s["text"] if isinstance(s, dict) else s
                        for s in item["leoSummary"]["sentences"]
                    ]

                # Store in MongoDB
                mongo_client.store_feed_items([item])

            except Exception as e:
                print(f"Error processing item: {e}")
                continue

        # Print final stats
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
        }

        print("\nFinal MongoDB Status:")
        print(f"Total items: {metrics['total_items']}")
        print(f"Pending items: {metrics['pending_items']}")
        print(f"Processed items: {metrics['processed_items']}")
        print(f"Filtered items: {metrics['filtered_items']}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
