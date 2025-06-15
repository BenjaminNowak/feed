import argparse
import os

from feed_aggregator.fetcher import FeedlyFetcher, URLFetcher
from feed_aggregator.processing.content_analyzer import ContentAnalyzer
from feed_aggregator.processing.llm_filter import LLMFilter
from feed_aggregator.storage.mongodb_client import MongoDBClient


def parse_args():
    parser = argparse.ArgumentParser(description="Process a Feedly article URL")
    parser.add_argument("url", help="Feedly article URL to process")
    parser.add_argument(
        "--category",
        default="Tech",
        help="Category to use for LLM analysis (default: Tech)",
    )
    return parser.parse_args()


def initialize_components(token, user_id, category):
    """Initialize all required components."""
    if not token:
        raise ValueError("FEEDLY_TOKEN environment variable not set")

    fetcher = FeedlyFetcher(token=token, user_id=user_id)
    content_analyzer = ContentAnalyzer()
    llm_filter = LLMFilter(provider="ollama", category=category)
    mongo_client = MongoDBClient()

    return fetcher, content_analyzer, llm_filter, mongo_client


def fetch_url_content(article):
    """Fetch content from article URL if available."""
    if "alternate" not in article or not article["alternate"]:
        return None

    url = (
        article["alternate"][0].get("href")
        if isinstance(article["alternate"], list)
        else None
    )
    if not url:
        return None

    try:
        url_fetcher = URLFetcher()
        url_content = url_fetcher.fetch_url_content(url)
        url_fetcher.close()

        if url_content:
            print("\nURL Content Fetched:")
            print(f"Title: {url_content.get('title', 'No title')}")
            print(f"Description: {url_content.get('description', 'No description')}")
            print(f"Main content length: {len(url_content.get('main_content', ''))}")
            return url_content

    except Exception as e:
        print(f"Error fetching URL content: {e}")
        return None


def combine_content(article, url_content):
    """Combine Feedly content with URL content."""
    feedly_content = article.get("content", {}).get(
        "content", article.get("summary", {}).get("content", "")
    )

    if not url_content:
        return feedly_content

    combined = feedly_content
    if url_content.get("main_content"):
        combined = f"{combined}\n\n{url_content['main_content']}"
    if url_content.get("description"):
        combined = f"{combined}\n\n{url_content['description']}"

    return combined


def run_content_analysis(analyzer, content):
    """Run content analysis and print results."""
    analysis = analyzer.analyze_item(
        {
            "content": content,
            "llm_analysis": {},  # Required by ContentAnalyzer
        }
    )

    print("\nContent Analysis Results:")
    print(f"Keywords: {analysis['keywords']}")
    print(f"Readability: {analysis['readability']}")
    print(f"Word count: {analysis['word_count']}")
    print(f"Reading time: {analysis['reading_time_minutes']:.1f} minutes")

    return analysis


def run_llm_analysis(analyzer, article, combined_content, url_content):
    """Run LLM analysis and print results."""
    analysis = analyzer.analyze_item(
        {
            "title": article.get("title", ""),
            "content": combined_content,
            "url_content_available": bool(url_content),
        }
    )

    print("\nLLM Analysis Results:")
    print(f"Relevance score: {analysis['relevance_score']}")
    print(f"Summary: {analysis['summary']}")
    print(f"Key topics: {analysis['key_topics']}")
    if analysis.get("filtered_reason"):
        print(f"Filtered reason: {analysis['filtered_reason']}")

    return analysis


def store_article(mongo_client, article, category, content_analysis, llm_analysis):
    """Store processed article in MongoDB."""
    try:
        article["category"] = category
        article["content_analysis"] = content_analysis
        article["llm_analysis"] = llm_analysis
        article["processing_status"] = "processed"

        mongo_client.store_feed_items([article])
        print(f"\nArticle stored in MongoDB with ID: {article['id']}")
        print(
            "To view details, run: python scripts/get_article_details.py",
            article["id"],
        )
    except Exception as e:
        print(f"Error storing article in MongoDB: {e}")


def main():
    args = parse_args()
    token = os.environ.get("FEEDLY_TOKEN")
    user_id = os.environ.get("FEEDLY_USER")

    # Initialize components
    fetcher, content_analyzer, llm_filter, mongo_client = initialize_components(
        token, user_id, args.category
    )

    try:
        # Fetch article
        article = fetcher.get_entry_by_url(args.url)
        print(f"Successfully fetched article: {article.get('title', 'No title')}")

        # Fetch and process URL content
        url_content = fetch_url_content(article)
        if url_content:
            article["url_content"] = url_content

        # Combine and analyze content
        combined_content = combine_content(article, url_content)
        content_analysis = run_content_analysis(content_analyzer, combined_content)
        llm_analysis = run_llm_analysis(
            llm_filter, article, combined_content, url_content
        )

        # Store results
        store_article(
            mongo_client, article, args.category, content_analysis, llm_analysis
        )

    # except Exception as e:
    #   print(f"Error processing article: {e}")
    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
