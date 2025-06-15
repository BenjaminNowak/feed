#!/usr/bin/env python3
"""Get detailed information about an article in MongoDB."""

import argparse

from feed_aggregator.storage.mongodb_client import MongoDBClient


def main():
    parser = argparse.ArgumentParser(description="Get article details from MongoDB")
    parser.add_argument("article_id", help="MongoDB article ID")
    args = parser.parse_args()

    # Connect to MongoDB
    client = MongoDBClient()

    try:
        # Query for the specific article
        article = client.feed_items.find_one({"id": args.article_id})

        if article:
            print("Article Details:")
            print(f"Title: {article.get('title', 'No title')}")
            print(f"Processing Status: {article.get('processing_status', 'Unknown')}")
            print(f"Published to Feed: {article.get('published_to_feed', False)}")
            print(f"Published Date: {article.get('published', 'Unknown')}")

            # Show content length
            content = ""
            if "content" in article and "content" in article["content"]:
                content = article["content"]["content"]
            elif "summary" in article and "content" in article["summary"]:
                content = article["summary"]["content"]

            print(f"Content Length: {len(content)} characters")
            print(f"Content Preview: {content[:200]}...")

            if "llm_analysis" in article:
                llm = article["llm_analysis"]
                print("\nLLM Analysis:")
                print(f"  Relevance Score: {llm.get('relevance_score', 'N/A')}")
                print(f"  Summary: {llm.get('summary', 'N/A')}")
                print(f"  Key Topics: {llm.get('key_topics', 'N/A')}")
                if llm.get("filtered_reason"):
                    print(f"  Filtered Reason: {llm.get('filtered_reason')}")

                # Show analysis metadata
                if "_analysis_metadata" in llm:
                    meta = llm["_analysis_metadata"]
                    print(f"  Model Used: {meta.get('model', 'Unknown')}")
                    print(f"  Provider: {meta.get('provider', 'Unknown')}")
                    print(f"  Category: {meta.get('category', 'Unknown')}")
                    print(f"  Config Path: {meta.get('config_path', 'Unknown')}")
                    print(f"  Timestamp: {meta.get('timestamp', 'Unknown')}")
            else:
                print("\nNo LLM analysis found")

        else:
            print(f"Article with ID '{args.article_id}' not found")

    finally:
        client.close()


if __name__ == "__main__":
    main()
