#!/usr/bin/env python3
"""Runner script for processing multiple categories in the ETL pipeline."""

import argparse
import sys
from datetime import datetime, timedelta, timezone

from feed_aggregator.config.category_config import CategoryConfig
from feed_aggregator.etl.process_category import git_commit_and_push, main
from feed_aggregator.etl.update_feed import main as update_feed_main
from feed_aggregator.storage.mongodb_client import MongoDBClient


def process_single_category(category_key: str) -> bool:
    """Process a single category.

    Args:
        category_key: Category to process

    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n{'='*60}")
        print(f"PROCESSING CATEGORY: {category_key}")
        print(f"{'='*60}")

        main(category_key)

        print(f"\n{'='*60}")
        print(f"COMPLETED CATEGORY: {category_key}")
        print(f"{'='*60}")

        return True
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR PROCESSING CATEGORY: {category_key}")
        print(f"Error: {e}")
        print(f"{'='*60}")
        return False


def process_all_categories() -> None:
    """Process all configured categories using round-robin approach."""
    try:
        from feed_aggregator.etl.process_category import (
            fetch_category_articles,
            process_pending_articles_round_robin,
        )

        category_config = CategoryConfig()
        all_categories = category_config.get_all_categories()

        print(f"Processing all categories: {all_categories}")
        print(
            "Using round-robin approach: fetch all articles first, then process in batches"
        )

        # Phase 1: Fetch articles from all categories
        print(f"\n{'='*60}")
        print("PHASE 1: FETCHING ARTICLES FROM ALL CATEGORIES")
        print(f"{'='*60}")

        total_fetched = 0
        fetch_failures = 0

        for category in all_categories:
            try:
                fetched_count = fetch_category_articles(category, category_config)
                total_fetched += fetched_count
                print(f"✓ {category}: {fetched_count} new articles")
            except Exception as e:
                print(f"✗ {category}: Failed to fetch articles - {e}")
                fetch_failures += 1

        print("\nFetch Summary:")
        print(f"Total new articles fetched: {total_fetched}")
        print(f"Categories with fetch failures: {fetch_failures}")

        # Phase 2: Process pending articles in round-robin fashion
        print(f"\n{'='*60}")
        print("PHASE 2: PROCESSING ARTICLES (ROUND-ROBIN)")
        print(f"{'='*60}")

        if total_fetched > 0:
            process_pending_articles_round_robin(all_categories, category_config)
        else:
            print("No new articles to process.")

        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total categories: {len(all_categories)}")
        print(f"Articles fetched: {total_fetched}")
        print(f"Fetch failures: {fetch_failures}")
        print(f"{'='*60}")

        if fetch_failures == len(all_categories):
            print("All categories failed to fetch articles!")
            sys.exit(1)

    except Exception as e:
        print(f"Error in multi-category processing: {e}")
        sys.exit(1)


def handle_list_categories():
    """Handle the --list option."""
    try:
        category_config = CategoryConfig()
        categories = category_config.get_all_categories()
        print("Available categories:")
        for category in categories:
            config = category_config.get_category_config(category)
            print(f"  {category}: {config['name']} - {config['description']}")
    except Exception as e:
        print(f"Error loading categories: {e}")
        sys.exit(1)


def validate_categories(categories):
    """Validate that specified categories exist."""
    try:
        category_config = CategoryConfig()
        available_categories = category_config.get_all_categories()

        for category in categories:
            if category not in available_categories:
                print(f"Error: Category '{category}' not found.")
                print(f"Available categories: {available_categories}")
                sys.exit(1)
    except Exception as e:
        print(f"Error loading category configuration: {e}")
        sys.exit(1)


def process_specific_categories(categories):
    """Process a list of specific categories."""
    success_count = 0
    failure_count = 0

    for category in categories:
        if process_single_category(category):
            success_count += 1
        else:
            failure_count += 1

    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Total categories processed: {len(categories)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failure_count}")
    print(f"{'='*60}")

    if failure_count > 0:
        sys.exit(1)


def _get_processed_articles(
    mongo_client, yesterday_start_ms, yesterday_end_ms, min_score
):
    """Get processed articles from the last 24 hours."""
    return list(
        mongo_client.feed_items.find(
            {
                "processing_status": {"$in": ["processed", "published"]},
                "llm_analysis.relevance_score": {"$gte": min_score},
                "$or": [
                    {
                        "published": {
                            "$gte": yesterday_start_ms,
                            "$lt": yesterday_end_ms,
                        }
                    },
                    {
                        "crawled": {
                            "$gte": yesterday_start_ms,
                            "$lt": yesterday_end_ms,
                        }
                    },
                ],
            }
        )
    )


def _get_xml_article_ids():
    """Get article IDs from existing XML feed."""
    import os

    from defusedxml import ElementTree as DefusedET

    xml_article_ids = set()
    if os.path.exists("feed.xml"):
        try:
            tree = DefusedET.parse("feed.xml")
            root = tree.getroot()
            channel = root.find("channel")

            for item in channel.findall("item"):
                guid_elem = item.find("guid")
                if guid_elem is not None and guid_elem.text:
                    xml_article_ids.add(guid_elem.text)

            print(f"Found {len(xml_article_ids)} articles already in XML feed")
        except Exception as e:
            print(f"Warning: Could not parse existing feed.xml: {e}")
    else:
        print("No existing feed.xml found")

    return xml_article_ids


def _find_missing_articles(processed_articles, xml_article_ids):
    """Find articles that are processed but not in XML."""
    missing_articles = []
    for article in processed_articles:
        if article["id"] not in xml_article_ids:
            missing_articles.append(article)
            title = article.get("title", "No title")[:50]
            article_id = article["id"][:20]
            print(f"  Missing: {title}... (ID: {article_id}...)")
    return missing_articles


def _show_sample_articles(processed_articles, xml_article_ids):
    """Show sample articles that were checked."""
    print("\nSample of processed articles checked:")
    for _i, article in enumerate(processed_articles[:3]):
        in_xml = "✓" if article["id"] in xml_article_ids else "✗"
        score = article.get("llm_analysis", {}).get("relevance_score", "N/A")
        title = article.get("title", "No title")[:50]
        print(f"  {in_xml} {title}... (Score: {score})")


def reconcile_processed_articles():
    """Reconcile last day's processed articles against XML feed and add missing ones."""
    try:
        print(f"\n{'='*60}")
        print("RECONCILING PROCESSED ARTICLES AGAINST XML FEED")
        print(f"{'='*60}")

        # Calculate last 24 hours ending now
        now = datetime.now(timezone.utc)
        yesterday_start = now - timedelta(days=1)
        yesterday_end = now

        print("Looking for articles processed between:")
        print(f"  Start: {yesterday_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  End: {yesterday_end.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Connect to MongoDB
        mongo_client = MongoDBClient()

        try:
            # Get configuration
            category_config = CategoryConfig()
            global_config = category_config.get_global_config()
            min_score = global_config.get("default_quality_threshold", 0.6)

            # Convert datetime to milliseconds for MongoDB query
            yesterday_start_ms = int(yesterday_start.timestamp() * 1000)
            yesterday_end_ms = int(yesterday_end.timestamp() * 1000)

            # Get processed articles
            processed_articles = _get_processed_articles(
                mongo_client, yesterday_start_ms, yesterday_end_ms, min_score
            )

            print(
                f"Found {len(processed_articles)} high-quality processed articles from yesterday"
            )

            if not processed_articles:
                print(
                    "No processed articles found from yesterday. Nothing to reconcile."
                )
                return

            # Get XML article IDs
            xml_article_ids = _get_xml_article_ids()

            # Find missing articles
            missing_articles = _find_missing_articles(
                processed_articles, xml_article_ids
            )
            print(
                f"Found {len(missing_articles)} processed articles missing from XML feed"
            )

            # Show sample articles
            _show_sample_articles(processed_articles, xml_article_ids)

            if missing_articles:
                # Mark missing articles as ready for publishing
                article_ids = [article["id"] for article in missing_articles]
                result = mongo_client.feed_items.update_many(
                    {"id": {"$in": article_ids}}, {"$unset": {"published_to_feed": ""}}
                )

                print(
                    f"Marked {result.modified_count} articles as ready for publishing"
                )

                # Update the XML feed
                print("Updating XML feed with missing articles...")
                update_feed_main()

                # Commit and push changes
                print("Committing and pushing changes...")
                git_commit_and_push()

                print(f"\n{'='*60}")
                print("RECONCILIATION COMPLETED SUCCESSFULLY")
                print(f"{'='*60}")
                print(f"Articles reconciled: {len(missing_articles)}")
                print("Feed updated and pushed to repository")
            else:
                print(
                    "All processed articles are already in the XML feed. No reconciliation needed."
                )

        finally:
            mongo_client.close()

    except Exception as e:
        print(f"Error during reconciliation: {e}")
        sys.exit(1)


def create_argument_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Process feed categories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a specific category
  python process_categories_runner.py ML

  # Process multiple specific categories
  python process_categories_runner.py ML Tech Cyber

  # Process all configured categories
  python process_categories_runner.py --all

  # List available categories
  python process_categories_runner.py --list

  # Reconcile yesterday's processed articles against XML feed
  python process_categories_runner.py --reconcile
        """,
    )

    parser.add_argument(
        "categories", nargs="*", help="Categories to process (e.g., ML, Tech, Cyber)"
    )

    parser.add_argument(
        "--all", action="store_true", help="Process all configured categories"
    )

    parser.add_argument(
        "--list", action="store_true", help="List all available categories"
    )

    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Reconcile last day's processed articles against XML feed and add missing ones",
    )

    return parser


def main_runner():
    """Main runner function."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle list option
    if args.list:
        handle_list_categories()
        return

    # Handle reconcile option
    if args.reconcile:
        if args.categories or args.all:
            print("Error: Cannot specify categories with --reconcile")
            sys.exit(1)
        reconcile_processed_articles()
        return

    # Handle all option
    if args.all:
        if args.categories:
            print("Error: Cannot specify both --all and specific categories")
            sys.exit(1)
        process_all_categories()
        return

    # Handle specific categories
    if not args.categories:
        print("Error: Must specify categories to process or use --all")
        parser.print_help()
        sys.exit(1)

    # Validate and process categories
    validate_categories(args.categories)
    process_specific_categories(args.categories)


if __name__ == "__main__":
    main_runner()
