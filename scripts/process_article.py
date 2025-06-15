import argparse
import os

from feed_aggregator.fetcher import FeedlyFetcher
from feed_aggregator.processing.content_analyzer import ContentAnalyzer
from feed_aggregator.processing.llm_filter import LLMFilter


def parse_args():
    parser = argparse.ArgumentParser(description="Process a Feedly article URL")
    parser.add_argument("url", help="Feedly article URL to process")
    parser.add_argument(
        "--category",
        default="Tech",
        help="Category to use for LLM analysis (default: Tech)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Initialize fetcher
    token = os.environ.get("FEEDLY_TOKEN")
    user_id = os.environ.get("FEEDLY_USER")

    if not token:
        raise ValueError("FEEDLY_TOKEN environment variable not set")

    fetcher = FeedlyFetcher(token=token, user_id=user_id)

    # Fetch the specific article
    entry_url = args.url
    try:
        article = fetcher.get_entry_by_url(entry_url)
        print(f"Successfully fetched article: {article.get('title', 'No title')}")
    except Exception as e:
        print(f"Error fetching article: {e}")
        return

    # Initialize analyzers
    content_analyzer = ContentAnalyzer()
    llm_filter = LLMFilter(
        provider="ollama", category=args.category
    )  # Using ollama with qwen3:32b

    try:
        # First run content analysis
        content_analysis = content_analyzer.analyze_item(
            {
                "content": article.get("content", {}).get(
                    "content", article.get("summary", {}).get("content", "")
                ),
                "llm_analysis": {},  # Required by ContentAnalyzer
            }
        )
        print("\nContent Analysis Results:")
        print(f"Keywords: {content_analysis['keywords']}")
        print(f"Readability: {content_analysis['readability']}")
        print(f"Word count: {content_analysis['word_count']}")
        print(f"Reading time: {content_analysis['reading_time_minutes']:.1f} minutes")

        # Then run LLM analysis
        llm_analysis = llm_filter.analyze_item(
            {
                "title": article.get("title", ""),
                "content": article.get("content", {}).get(
                    "content", article.get("summary", {}).get("content", "")
                ),
            }
        )
        print("\nLLM Analysis Results:")
        print(f"Relevance score: {llm_analysis['relevance_score']}")
        print(f"Summary: {llm_analysis['summary']}")
        print(f"Key topics: {llm_analysis['key_topics']}")
        if llm_analysis.get("filtered_reason"):
            print(f"Filtered reason: {llm_analysis['filtered_reason']}")

    except Exception as e:
        print(f"Error during analysis: {e}")


if __name__ == "__main__":
    main()
