#!/usr/bin/env python3
import argparse
from typing import Dict, Optional

from feed_aggregator.processing.llm_filter import LLMFilter
from feed_aggregator.storage.mongodb_client import MongoDBClient


def get_most_recent_item(mongo_client: MongoDBClient) -> Optional[Dict]:
    """Get most recent item from MongoDB."""
    return mongo_client.feed_items.find_one(sort=[("crawled", -1)])


def extract_content(item: Dict) -> Dict:
    """Extract title and content from item."""
    content = item.get("content", {}).get("content", "")
    if isinstance(content, dict):
        content = content.get("content", "")

    return {"title": item.get("title", ""), "content": content}


def main():
    parser = argparse.ArgumentParser(description="Process feed item with LLM")
    parser.add_argument(
        "--provider",
        choices=["openai", "ollama"],
        default="ollama",
        help="LLM provider to use (default: ollama)",
    )
    args = parser.parse_args()

    # Initialize MongoDB client
    mongo_client = MongoDBClient()

    try:
        # Get most recent item
        item = get_most_recent_item(mongo_client)
        if not item:
            print("No items found in MongoDB")
            return

        print(f"\nProcessing item: {item['title']}")
        print(f"Source: {item.get('origin', {}).get('title', 'Unknown')}")
        print(f"URL: {item.get('originId', 'No URL')}\n")

        # Initialize LLM filter
        llm = LLMFilter(provider=args.provider)

        # Extract content and process with LLM
        content = extract_content(item)
        result = llm.analyze_item(content)

        # Print analysis results
        print("LLM Analysis Results:")
        print("=" * 80)
        print(f"Relevance Score: {result['relevance_score']:.2f}")
        print(f"Summary: {result['summary']}")
        print(f"Key Topics: {', '.join(result['key_topics'])}")
        if result.get("filtered_reason"):
            print(f"Filtered Reason: {result['filtered_reason']}")

        # Update MongoDB with analysis results
        mongo_client.feed_items.update_one(
            {"_id": item["_id"]},
            {"$set": {"llm_analysis": result, "processing_status": "processed"}},
        )
        print("\nAnalysis results saved to MongoDB")

    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
