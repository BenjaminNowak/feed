import os
import subprocess  # nosec B404 - Used for controlled git operations
from datetime import datetime
from typing import Optional

from feed_aggregator.config.category_config import CategoryConfig
from feed_aggregator.config.logging_config import setup_logging
from feed_aggregator.etl import update_feed
from feed_aggregator.fetcher import FeedlyFetcher, URLFetcher
from feed_aggregator.processing.content_analyzer import ContentAnalyzer
from feed_aggregator.processing.llm_filter import LLMFilter
from feed_aggregator.storage.mongodb_client import MongoDBClient

# Set up logger
logger = setup_logging(__name__)


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
        logger.info(f"Successfully committed and pushed feed update at {timestamp}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during git operations: {e}")


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
    logger.debug(f"Available categories: {available_categories}")

    feedly_category = category_config.get_feedly_category(category_key)
    if feedly_category not in available_categories:
        raise ValueError(f"Category '{feedly_category}' not found in Feedly")

    logger.info(f"Fetching from category: {feedly_category}")

    global_config = category_config.get_global_config()
    fetch_count = global_config.get("default_fetch_count", 100)

    data = fetcher.get_stream_contents(
        f"user/{user_id}/category/{feedly_category}", count=fetch_count
    )
    logger.info(f"Fetched {len(data['items'])} items")
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
    existing_item = mongo_client.get_item(item["id"])
    if existing_item and "llm_analysis" in existing_item:
        logger.debug("Item already analyzed, skipping...")
        return None

    # Get all available content
    feedly_content = item.get("content", {}).get(
        "content", item.get("summary", {}).get("content", "")
    )
    url_content = item.get("url_content", {})

    # Combine content for analysis
    combined_content = feedly_content
    if url_content:
        if url_content.get("main_content"):
            combined_content = f"{combined_content}\n\n{url_content['main_content']}"
        if url_content.get("description"):
            combined_content = f"{combined_content}\n\n{url_content['description']}"

    # Run content analysis
    content_analysis = content_analyzer.analyze_item(
        {"content": combined_content, "llm_analysis": {}}
    )

    # Run LLM analysis with all available content
    llm_analysis = llm_filter.analyze_item(
        {
            "title": item.get("title", ""),
            "content": combined_content,
            "url_content_available": bool(url_content),
        }
    )

    # Add analyses to item
    item["content_analysis"] = content_analysis
    item["llm_analysis"] = llm_analysis
    item["processing_status"] = mongo_client.STATUS_PROCESSED

    # Print analysis results
    relevance_score = llm_analysis["relevance_score"]
    logger.debug(f"Relevance score: {relevance_score} (threshold: {quality_threshold})")

    if llm_analysis.get("filtered_reason"):
        logger.info(f"Filtered reason: {llm_analysis['filtered_reason']}")
        item["processing_status"] = mongo_client.STATUS_FILTERED
        return 0  # Not high quality

    if relevance_score >= quality_threshold:  # Use category-specific threshold
        logger.info("High quality article found!")
        return 1  # High quality

    return 0  # Not high quality


def _clean_item_data(item):
    """Clean up item data before storing and fetch URL content."""
    # Clean up leoSummary if present
    if "leoSummary" in item and "sentences" in item["leoSummary"]:
        # Convert sentence objects to strings
        item["leoSummary"]["sentences"] = [
            s["text"] if isinstance(s, dict) else s
            for s in item["leoSummary"]["sentences"]
        ]

    # Fetch URL content if available
    if "alternate" in item and item["alternate"]:
        url = (
            item["alternate"][0].get("href")
            if isinstance(item["alternate"], list)
            else None
        )
        if url:
            try:
                url_fetcher = URLFetcher()
                url_content = url_fetcher.fetch_url_content(url)
                if url_content:
                    item["url_content"] = url_content
                url_fetcher.close()
            except Exception as e:
                logger.error(f"Error fetching URL content: {e}", exc_info=True)


def fetch_category_articles(category_key: str, category_config: CategoryConfig) -> int:
    """Fetch articles from a category and store them in MongoDB.

    Args:
        category_key: Category to fetch from
        category_config: Category configuration instance

    Returns:
        Number of new articles fetched
    """
    try:
        logger.info(f"{'='*50}")
        logger.info(f"FETCHING ARTICLES FROM: {category_key}")
        logger.info(f"{'='*50}")

        # Initialize fetcher and mongo client
        token = os.environ.get("FEEDLY_TOKEN")
        user_id = os.environ.get("FEEDLY_USER")

        if not token:
            raise ValueError("FEEDLY_TOKEN environment variable not set")

        fetcher = FeedlyFetcher(token=token, user_id=user_id)
        mongo_client = MongoDBClient()

        # Get category data
        data = _get_category_data(fetcher, user_id, category_key, category_config)

        new_articles = 0
        for item in data["items"]:
            # Check if item already exists
            if mongo_client.item_exists(item["id"]):
                continue

            # Add category and processing status
            item["category"] = category_key
            item["processing_status"] = mongo_client.STATUS_PENDING

            # Clean up and store item
            _clean_item_data(item)
            mongo_client.store_feed_items([item])
            new_articles += 1

        logger.info(f"Fetched {new_articles} new articles from {category_key}")
        mongo_client.close()
        return new_articles

    except Exception as e:
        logger.error(f"Error fetching from {category_key}: {e}", exc_info=True)
        return 0


def _initialize_category_components(categories: list, category_config: CategoryConfig):
    """Initialize components for each category."""
    category_components = {}
    category_stats = {}

    for category_key in categories:
        try:
            _, content_analyzer, llm_filter, mongo_client = _initialize_components(
                category_key, category_config
            )
            category_components[category_key] = {
                "content_analyzer": content_analyzer,
                "llm_filter": llm_filter,
                "mongo_client": mongo_client,
                "quality_threshold": category_config.get_quality_threshold(
                    category_key
                ),
                "high_quality_target": category_config.get_high_quality_target(
                    category_key
                ),
                "high_quality_count": 0,
            }
            category_stats[category_key] = {
                "processed": 0,
                "high_quality": 0,
                "filtered": 0,
            }
        except Exception as e:
            logger.error(
                f"Error initializing components for {category_key}: {e}", exc_info=True
            )
            continue

    return category_components, category_stats


def _process_category_batch(
    category_key: str, components: dict, category_stats: dict, batch_size: int
) -> int:
    """Process a batch of articles for a single category."""
    mongo_client = components["mongo_client"]

    # Get pending articles for this category
    pending_articles = mongo_client.get_items_by_status(
        status=mongo_client.STATUS_PENDING, category=category_key, limit=batch_size
    )

    if not pending_articles:
        return 0

    logger.info(f"Processing {len(pending_articles)} articles from {category_key}")
    articles_processed = 0

    for item in pending_articles:
        try:
            quality_result = _process_single_item(
                item,
                components["content_analyzer"],
                components["llm_filter"],
                mongo_client,
                components["quality_threshold"],
            )

            if quality_result is None:
                continue

            # Update item in database
            update_data = {
                "content_analysis": item.get("content_analysis"),
                "llm_analysis": item.get("llm_analysis"),
                "processing_status": item.get("processing_status"),
            }

            # Include URL content if available
            if "url_content" in item:
                update_data["url_content"] = item["url_content"]

            mongo_client.update_item(item["id"], update_data)

            # Update stats
            category_stats[category_key]["processed"] += 1
            if quality_result == 1:
                category_stats[category_key]["high_quality"] += 1
                components["high_quality_count"] += 1

                # Check if we should update feed
                target = components["high_quality_target"]
                if components["high_quality_count"] >= target:
                    logger.info(
                        f"{category_key}: Found {target} high quality articles - "
                        "updating feed..."
                    )
                    update_feed.main()
                    git_commit_and_push()
                    components["high_quality_count"] = 0
            else:
                category_stats[category_key]["filtered"] += 1

            articles_processed += 1

        except Exception as e:
            logger.error(
                f"Error processing article from {category_key}: {e}", exc_info=True
            )
            continue

    return articles_processed


def _print_processing_statistics(category_stats: dict, category_components: dict):
    """Print final processing statistics."""
    logger.info(f"{'='*60}")
    logger.info("FINAL PROCESSING STATISTICS")
    logger.info(f"{'='*60}")

    for category_key, stats in category_stats.items():
        if category_key in category_components:
            logger.info(f"{category_key}:")
            logger.info(f"  Processed: {stats['processed']}")
            logger.info(f"  High Quality: {stats['high_quality']}")
            logger.info(f"  Filtered: {stats['filtered']}")


def process_pending_articles_round_robin(
    categories: list, category_config: CategoryConfig
):
    """Process pending articles from all categories in round-robin fashion.

    Args:
        categories: List of category keys to process
        category_config: Category configuration instance
    """
    logger.info(f"{'='*60}")
    logger.info("PROCESSING PENDING ARTICLES (ROUND-ROBIN)")
    logger.info(f"{'='*60}")

    # Initialize components for each category
    category_components, category_stats = _initialize_category_components(
        categories, category_config
    )

    # Round-robin processing
    batch_size = 5  # Process 5 articles per category per round
    total_processed = 0

    while True:
        articles_processed_this_round = 0

        for category_key in categories:
            if category_key not in category_components:
                continue

            components = category_components[category_key]
            processed = _process_category_batch(
                category_key, components, category_stats, batch_size
            )
            articles_processed_this_round += processed
            total_processed += processed

        # If no articles were processed this round, we're done
        if articles_processed_this_round == 0:
            break

        logger.info(f"Round completed. Total processed: {total_processed}")

    # Print final statistics and close connections
    _print_processing_statistics(category_stats, category_components)

    # Close all connections
    for components in category_components.values():
        components["mongo_client"].close()


def _print_final_stats(mongo_client):
    """Print final MongoDB statistics."""
    metrics = mongo_client.get_status_counts()

    logger.info("Final MongoDB Status:")
    logger.info(f"Total items: {metrics['total']}")
    logger.info(f"Pending items: {metrics['pending']}")
    logger.info(f"Processed items: {metrics['processed']}")
    logger.info(f"Filtered items: {metrics['filtered']}")
    logger.info(f"Published items: {metrics['published']}")


def _process_pending_articles_step(
    category_key: str, category_config: CategoryConfig, mongo_client
) -> None:
    """Step 2: Process all pending articles from MongoDB."""
    logger.info(f"{'='*50}")
    logger.info("STEP 2: PROCESSING PENDING ARTICLES FROM MONGODB")
    logger.info(f"{'='*50}")

    # Get all pending articles for this category from MongoDB
    pending_articles = mongo_client.get_items_by_status(
        status=mongo_client.STATUS_PENDING,
        category=category_key,
        sort_field="published",
    )

    logger.info(f"Found {len(pending_articles)} pending articles to process")

    if len(pending_articles) == 0:
        logger.info("No pending articles to process")
        return

    # Initialize components for processing
    _, content_analyzer, llm_filter, _ = _initialize_components(
        category_key, category_config
    )

    quality_threshold = category_config.get_quality_threshold(category_key)
    high_quality_target = category_config.get_high_quality_target(category_key)
    high_quality_count = 0

    # Process each pending article
    for i, item in enumerate(pending_articles, 1):
        logger.info(f"Processing item {i}/{len(pending_articles)}")
        logger.info(f"Title: {item.get('title', 'No title')}")

        try:
            quality_result = _process_single_item(
                item, content_analyzer, llm_filter, mongo_client, quality_threshold
            )

            if quality_result is None:  # Item was skipped (already analyzed)
                continue

            # Update the item in MongoDB with analysis results
            update_data = {
                "content_analysis": item.get("content_analysis"),
                "llm_analysis": item.get("llm_analysis"),
                "processing_status": item.get("processing_status"),
            }

            # Include URL content if available
            if "url_content" in item:
                update_data["url_content"] = item["url_content"]

            mongo_client.update_item(item["id"], update_data)

            if quality_result == 1:  # High quality
                high_quality_count += 1
                logger.info(
                    f"High quality article found! (Total: {high_quality_count})"
                )

                # If we've found enough high quality articles, update feed
                if high_quality_count == high_quality_target:
                    logger.info(
                        f"Found {high_quality_target} high quality articles - updating feed..."
                    )
                    update_feed.main()
                    git_commit_and_push()
                    high_quality_count = 0  # Reset counter

        except Exception as e:
            logger.error(f"Error processing item: {e}", exc_info=True)
            continue


def _publish_unpublished_articles_step(
    category_key: str, category_config: CategoryConfig, mongo_client
) -> None:
    """Step 3: Always check for and publish any high-quality articles that haven't been published yet."""
    logger.info(f"{'='*50}")
    logger.info("STEP 3: PUBLISHING PENDING HIGH-QUALITY ARTICLES")
    logger.info(f"{'='*50}")

    # Check if there are any high-quality processed articles that haven't been published
    quality_threshold = category_config.get_quality_threshold(category_key)
    unpublished_articles = mongo_client.get_filtered_items(
        min_score=quality_threshold, category=category_key
    )

    if unpublished_articles:
        logger.info(
            f"Found {len(unpublished_articles)} unpublished high-quality articles"
        )
        logger.info("Updating feed with pending articles...")
        update_feed.main()
        git_commit_and_push()
    else:
        logger.info("No unpublished high-quality articles found")


def main(category_key: Optional[str] = None):
    """Main processing function.

    Args:
        category_key: Category to process (e.g., 'ML', 'Tech').
                     If None, defaults to 'ML' for backward compatibility.
    """
    if category_key is None:
        category_key = "ML"  # Default for backward compatibility

    try:
        # Load category configuration
        category_config = CategoryConfig()

        logger.info(f"Processing category: {category_key}")
        logger.debug(f"Available categories: {category_config.get_all_categories()}")

        # Get category-specific settings
        quality_threshold = category_config.get_quality_threshold(category_key)
        high_quality_target = category_config.get_high_quality_target(category_key)
        output_feed = category_config.get_output_feed(category_key)

        logger.debug(f"Quality threshold: {quality_threshold}")
        logger.debug(f"High quality target: {high_quality_target}")
        logger.debug(f"Output feed: {output_feed}")

        # Step 1: Fetch new articles from Feedly and store them in MongoDB
        logger.info(f"{'='*50}")
        logger.info("STEP 1: FETCHING NEW ARTICLES FROM FEEDLY")
        logger.info(f"{'='*50}")

        new_articles_count = fetch_category_articles(category_key, category_config)
        logger.info(f"Fetched {new_articles_count} new articles from Feedly")

        # Initialize MongoDB client for steps 2 and 3
        _, _, _, mongo_client = _initialize_components(category_key, category_config)

        # Step 2: Process all pending articles from MongoDB
        _process_pending_articles_step(category_key, category_config, mongo_client)

        # Step 3: Publish any unpublished high-quality articles
        _publish_unpublished_articles_step(category_key, category_config, mongo_client)

        # Print final stats
        _print_final_stats(mongo_client)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        if "mongo_client" in locals():
            mongo_client.close()


if __name__ == "__main__":
    import sys

    # Allow category to be passed as command line argument
    category = sys.argv[1] if len(sys.argv) > 1 else None
    main(category)
