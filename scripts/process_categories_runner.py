#!/usr/bin/env python3
"""Runner script for processing multiple categories in the ETL pipeline."""

import argparse
import sys

from feed_aggregator.config.category_config import CategoryConfig
from feed_aggregator.etl.process_category import main


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
    """Process all configured categories."""
    try:
        category_config = CategoryConfig()
        all_categories = category_config.get_all_categories()

        print(f"Processing all categories: {all_categories}")

        success_count = 0
        failure_count = 0

        for category in all_categories:
            if process_single_category(category):
                success_count += 1
            else:
                failure_count += 1

        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total categories: {len(all_categories)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {failure_count}")
        print(f"{'='*60}")

        if failure_count > 0:
            sys.exit(1)

    except Exception as e:
        print(f"Error loading category configuration: {e}")
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

    return parser


def main_runner():
    """Main runner function."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle list option
    if args.list:
        handle_list_categories()
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
