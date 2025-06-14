import os
import subprocess  # nosec B404 - Used for controlled git operations
from datetime import datetime
from typing import Optional

from feed_aggregator.config.category_config import CategoryConfig
from feed_aggregator.etl import update_feed
from feed_aggregator.fetcher import FeedlyFetcher
from feed_aggregator.processing.content_analyzer import ContentAnalyzer
from feed_aggregator.processing.llm_filter import LLMFilter
from feed_aggregator.storage.mongodb_client import MongoDBClient


def git_commit_and_push():
    """Commit and push feed.xml changes with timestamp."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(
            ["git", "add", "feed.xml"], check=True
        )  # nosec B603, B607 - Controlled git command
        subprocess.run(
            ["git", "commit", "-m", f"Update feed: {timestamp}"], check=True
        )  # nosec B603, B607 - Controlled git command
        subprocess.run(
            ["git", "push"], check=True
        )  # nosec B603, B607 - Controlled git command
        print(f"Successfully committed and pushed feed update at {timestamp}")
    except subprocess.CalledProcessError as e:
        print(f"Error during git operations: {e}")


def _initialize_components(category_key: str, category_config: CategoryConfig):
    """Initialize fetcher, analyzers, and database client.

    Args:
        category_key: Category key (e.g., 'ML', 'Tech')
        category_config: Category configuration instance
    """
    token = os.environ.get("FEEDLY_TOKEN")
    user_id = os.environ.get("FEEDLY_USER")

    if not token:
        raise ValueError("FEEDLY_TOKEN environment variable not set")

    fetcher = FeedlyFetcher(token=token, user_id=user_id)
    content_analyzer = ContentAnalyzer()

    # Get category-specific prompts path
    prompts_path = category_config.get_prompts_path(category_key)
    global_config = category_config.get_global_config()
    provider = global_config.get("default_provider", "ollama")

    llm_filter = LLMFilter(provider=provider, config_path=prompts_path)
    mongo_client = MongoDBClient()

    return fetcher, content_analyzer, llm_filter, mongo_client


def _get_category_data(
    fetcher, user_id, category_key: str, category_config: CategoryConfig
):
    """Get data from the specified category.

    Args:
        fetcher: FeedlyFetcher instance
        user_id: Feedly user ID
        category_key: Category key (e.g., 'ML', 'Tech')
        category_config: Category configuration instance
    """
    available_categories = list(fetcher.session.user.user_categories.name2stream.keys())
    print(f"Available categories: {available_categories}")

    feedly_category = category_config.get_feedly_category(category_key)
    if feedly_category not in available_categories:
        raise ValueError(f"Category '{feedly_category}' not found in Feedly")

    print(f"\nFetching from category: {feedly_category}")

    global_config = category_config.get_global_config()
    fetch_count = global_config.get("default_fetch_count", 100)

    data = fetcher.get_stream_contents(
        f"user/{user_id}/category/{feedly_category}", count=fetch_count
    )
    print(f"\nFetched {len(data['items'])} items")
    return data


def _process_single_item(
    item, content_analyzer, llm_filter, mongo_client, quality_threshold: float
):
    """Process a single feed item.

    Args:
        item: Feed item to process
        content_analyzer: Content analyzer instance
        llm_filter: LLM filter instance
        mongo_client: MongoDB client
        quality_threshold: Quality threshold for the category
    """
    # Check if item exists and has been analyzed
    existing_item = mongo_client.feed_items.find_one({"id": item["id"]})
    if existing_item and "llm_analysis" in existing_item:
        print("Item already analyzed, skipping...")
        return None

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
    relevance_score = llm_analysis["relevance_score"]
    print(f"Relevance score: {relevance_score} (threshold: {quality_threshold})")

    if llm_analysis.get("filtered_reason"):
        print(f"Filtered reason: {llm_analysis['filtered_reason']}")
        item["processing_status"] = "filtered_out"
        return 0  # Not high quality

    if relevance_score >= quality_threshold:  # Use category-specific threshold
        print("High quality article found!")
        return 1  # High quality

    return 0  # Not high quality


def _clean_item_data(item):
    """Clean up item data before storing."""
    if "leoSummary" in item and "sentences" in item["leoSummary"]:
        # Convert sentence objects to strings
        item["leoSummary"]["sentences"] = [
            s["text"] if isinstance(s, dict) else s
            for s in item["leoSummary"]["sentences"]
        ]


def _print_final_stats(mongo_client):
    """Print final MongoDB statistics."""
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


def main(category_key: Optional[str] = None):
    """Main processing function.

    Args:
        category_key: Category to process (e.g., 'ML', 'Tech').
                     If None, defaults to 'ML' for backward compatibility.
    """
    if category_key is None:
        category_key = "ML"  # Default for backward compatibility

    high_quality_count = 0

    try:
        # Load category configuration
        category_config = CategoryConfig()

        print(f"Processing category: {category_key}")
        print(f"Available categories: {category_config.get_all_categories()}")

        # Get category-specific settings
        quality_threshold = category_config.get_quality_threshold(category_key)
        high_quality_target = category_config.get_high_quality_target(category_key)
        output_feed = category_config.get_output_feed(category_key)

        print(f"Quality threshold: {quality_threshold}")
        print(f"High quality target: {high_quality_target}")
        print(f"Output feed: {output_feed}")

        # Initialize components
        fetcher, content_analyzer, llm_filter, mongo_client = _initialize_components(
            category_key, category_config
        )

        # Get category data
        user_id = os.environ.get("FEEDLY_USER")
        data = _get_category_data(fetcher, user_id, category_key, category_config)

        # Process each item
        for i, item in enumerate(data["items"], 1):
            print(f"\nProcessing item {i}/{len(data['items'])}")
            print(f"Title: {item.get('title', 'No title')}")

            try:
                quality_result = _process_single_item(
                    item, content_analyzer, llm_filter, mongo_client, quality_threshold
                )

                if quality_result is None:  # Item was skipped
                    continue

                if quality_result == 1:  # High quality
                    high_quality_count += 1
                    print(f"High quality article found! (Total: {high_quality_count})")

                    # If we've found enough high quality articles, update feed
                    if high_quality_count == high_quality_target:
                        print(
                            f"\nFound {high_quality_target} high quality articles - updating feed..."
                        )
                        update_feed.main()
                        git_commit_and_push()
                        high_quality_count = 0  # Reset counter

                # Clean up and store item
                _clean_item_data(item)
                mongo_client.store_feed_items([item])

            except Exception as e:
                print(f"Error processing item: {e}")
                continue

        # Print final stats
        _print_final_stats(mongo_client)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if "mongo_client" in locals():
            mongo_client.close()


if __name__ == "__main__":
    import sys

    # Allow category to be passed as command line argument
    category = sys.argv[1] if len(sys.argv) > 1 else None
    main(category)
