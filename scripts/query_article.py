#!/usr/bin/env python3
"""Query MongoDB for a specific article."""

import argparse
import json

from bson import json_util

from feed_aggregator.storage.mongodb_client import MongoDBClient


def parse_args():
    parser = argparse.ArgumentParser(description="Query MongoDB for a specific article")
    parser.add_argument("url", help="Feedly article URL to query")
    parser.add_argument(
        "--full", action="store_true", help="Display full document content"
    )
    return parser.parse_args()


def extract_id_from_url(url: str) -> str:
    """Extract the Feedly ID from the URL."""
    # URL format: https://feedly.com/i/entry/ID
    if "/i/entry/" in url:
        return url.split("/i/entry/")[1]
    return url


def main():
    args = parse_args()

    # Extract the ID from the URL
    feedly_id = extract_id_from_url(args.url)
    print(f"Searching for article with ID: {feedly_id}")

    # Connect to MongoDB
    client = MongoDBClient()

    try:
        # Query for the specific article
        article = client.feed_items.find_one({"id": feedly_id})

        if article:
            print("\nArticle found in MongoDB:")
            print(f"Title: {article.get('title', 'No title')}")
            print(f"Processing Status: {article.get('processing_status', 'Unknown')}")
            print(f"Published to Feed: {article.get('published_to_feed', False)}")

            if "llm_analysis" in article:
                llm = article["llm_analysis"]
                print("\nLLM Analysis:")
                print(f"  Relevance Score: {llm.get('relevance_score', 'N/A')}")
                print(f"  Summary: {llm.get('summary', 'N/A')}")
                print(f"  Key Topics: {llm.get('key_topics', 'N/A')}")
                if llm.get("filtered_reason"):
                    print(f"  Filtered Reason: {llm.get('filtered_reason')}")
            else:
                print("\nNo LLM analysis found")

            # Show either full document or just the keys
            if args.full:
                print("\nFull document content:")
                print(json.dumps(json.loads(json_util.dumps(article)), indent=2))
            else:
                print(f"\nFull document keys: {list(article.keys())}")

        else:
            print(f"\nArticle with ID '{feedly_id}' not found in MongoDB")

            # Let's also search by title
            print("\nSearching by title 'Make Self-XSS Great Again'...")
            by_title = list(
                client.feed_items.find(
                    {"title": {"$regex": "Make Self-XSS Great Again", "$options": "i"}},
                    {
                        "id": 1,
                        "title": 1,
                        "processing_status": 1,
                        "published_to_feed": 1,
                        "llm_analysis.relevance_score": 1,
                    },
                ).limit(5)
            )

            if by_title:
                print("Found articles with matching title:")
                for item in by_title:
                    print(f"  ID: {item['id']}")
                    print(f"  Title: {item.get('title', 'No title')}")
                    print(f"  Status: {item.get('processing_status', 'Unknown')}")
                    print(f"  Published: {item.get('published_to_feed', False)}")
                    if (
                        "llm_analysis" in item
                        and "relevance_score" in item["llm_analysis"]
                    ):
                        print(
                            f"  Relevance Score: {item['llm_analysis']['relevance_score']}"
                        )
                    print()
            else:
                print("No articles found with that title")

            # Let's also search by partial ID match
            print("Searching for similar IDs...")
            similar = list(
                client.feed_items.find(
                    {"id": {"$regex": feedly_id.split("=")[0]}}, {"id": 1, "title": 1}
                ).limit(5)
            )

            if similar:
                print("Found similar articles:")
                for item in similar:
                    print(f"  ID: {item['id']}")
                    print(f"  Title: {item.get('title', 'No title')}")
            else:
                print("No similar articles found")

    finally:
        client.close()


if __name__ == "__main__":
    main()
