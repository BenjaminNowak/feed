#!/usr/bin/env python3
"""
Setup training data for Cyber category using existing MongoDB articles.
"""

import logging

from feed_aggregator.processing.prompt_tuner import PromptTuner
from feed_aggregator.storage.mongodb_client import MongoDBClient

logging.basicConfig(level=logging.INFO)


def setup_training_data():
    """Setup training data using existing articles."""
    print("🔧 Setting up Cyber category training data")
    print("=" * 50)

    # Connect to MongoDB to find some articles
    mongo_client = MongoDBClient()

    try:
        # Find some articles to use as training data
        articles = list(
            mongo_client.feed_items.find(
                {
                    "processing_status": {"$in": ["processed", "published"]},
                    "llm_analysis": {"$exists": True},
                }
            ).limit(10)
        )

        print(f"📊 Found {len(articles)} processed articles in MongoDB")

        if len(articles) < 5:
            print(
                "❌ Need at least 5 articles for training. Process more articles first."
            )
            return

        # Prepare training data
        article_ids = []
        target_scores = []
        rationales = []

        for article in articles:
            article_id = article["id"]
            title = article.get("title", "")
            current_score = article.get("llm_analysis", {}).get("relevance_score", 0.5)
            content_length = len(article.get("content", {}).get("content", ""))

            # Assign target scores based on content analysis
            if "reddit" in title.lower() or content_length < 200:
                # Low quality - Reddit posts or very short content
                target_score = 0.2
                rationale = "Low quality content - Reddit post or very short content lacking technical depth"
            elif current_score > 0.8:
                # Keep high scores if they seem legitimate
                target_score = 0.8
                rationale = "High quality technical content with substantial cybersecurity analysis"
            elif current_score < 0.4:
                # Keep low scores
                target_score = 0.3
                rationale = "Low to medium quality content with limited technical value"
            else:
                # Medium quality
                target_score = 0.6
                rationale = "Medium quality content with some technical insights but room for improvement"

            article_ids.append(article_id)
            target_scores.append(target_score)
            rationales.append(rationale)

            print(f"   {title[:50]}... -> Target: {target_score}")

        # Add training data
        tuner = PromptTuner("Cyber", "ollama")

        try:
            tuner.collect_training_data(article_ids, target_scores, rationales)

            # Show final count
            training_count = len(tuner.get_training_data())
            print(f"\n✅ Added training data. Total examples: {training_count}")

            if training_count >= 5:
                print("\n🚀 Ready to run tuning experiment!")
                print(
                    "Run: python3 scripts/tune_prompts.py tune Cyber --iterations 3 --population 4"
                )

        finally:
            tuner.close()

    finally:
        mongo_client.close()


if __name__ == "__main__":
    setup_training_data()
