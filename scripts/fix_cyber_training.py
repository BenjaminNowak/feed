#!/usr/bin/env python3
"""
Fix Cyber category training data by using only Cyber-specific articles.
"""

import logging

from feed_aggregator.processing.prompt_tuner import PromptTuner
from feed_aggregator.storage.mongodb_client import MongoDBClient

logging.basicConfig(level=logging.INFO)


def clear_and_setup_cyber_training():
    """Clear incorrect training data and setup proper Cyber category training."""
    print("🔧 Fixing Cyber category training data")
    print("=" * 50)

    # Connect to MongoDB
    mongo_client = MongoDBClient()
    tuner = PromptTuner("Cyber", "ollama")

    try:
        # Clear existing training data for Cyber category
        result = tuner.training_data.delete_many({"category": "Cyber"})
        print(f"🗑️  Cleared {result.deleted_count} existing Cyber training records")

        # Look for actual cybersecurity-related articles
        cyber_keywords = [
            "security",
            "vulnerability",
            "exploit",
            "malware",
            "ransomware",
            "phishing",
            "breach",
            "hack",
            "cyber",
            "threat",
            "attack",
            "penetration",
            "firewall",
            "encryption",
            "authentication",
            "CVE",
            "zero-day",
            "backdoor",
            "botnet",
        ]

        # Build query to find cyber-related articles
        cyber_query = {
            "processing_status": {"$in": ["processed", "published"]},
            "llm_analysis": {"$exists": True},
            "$or": [
                {"title": {"$regex": "|".join(cyber_keywords), "$options": "i"}},
                {
                    "content.content": {
                        "$regex": "|".join(cyber_keywords[:5]),
                        "$options": "i",
                    }
                },  # Limit regex complexity
            ],
        }

        articles = list(mongo_client.feed_items.find(cyber_query).limit(15))
        print(f"📊 Found {len(articles)} cyber-related articles in MongoDB")

        if len(articles) < 5:
            print("❌ Not enough cyber-related articles found.")
            print("Let's use the published Self-XSS article as an example:")

            # Use the Self-XSS article we know exists
            xss_article = mongo_client.feed_items.find_one(
                {"title": {"$regex": "Self-XSS", "$options": "i"}}
            )

            if xss_article:
                print(f"✅ Found Self-XSS article: {xss_article['title']}")

                # Add it as training data with corrected target score
                tuner.collect_training_data(
                    article_ids=[xss_article["id"]],
                    target_scores=[0.3],  # Should be low-medium, not high
                    rationales=[
                        "Reddit post with minimal content - should score low despite security topic"
                    ],
                )

                print("📝 Added Self-XSS article as training example")
                print("⚠️  Need more cyber articles to run full tuning experiment")
                print("\nTo add more training data manually:")
                print("python3 scripts/tune_prompts.py add-training Cyber \\")
                print("  --articles 'article_id_1,article_id_2' \\")
                print("  --scores '0.2,0.8' \\")
                print("  --rationales 'Low quality post,High quality analysis'")
            else:
                print("❌ No cyber-related articles found at all")
            return

        # Prepare training data from cyber articles
        article_ids = []
        target_scores = []
        rationales = []

        for article in articles:
            article_id = article["id"]
            title = article.get("title", "")
            article.get("llm_analysis", {}).get("relevance_score", 0.5)
            content = article.get("content", {}).get("content", "")
            content_length = len(content)

            # More sophisticated scoring for cyber content
            if (
                any(keyword in title.lower() for keyword in ["reddit", "submitted by"])
                or content_length < 200
            ):
                # Low quality - Reddit posts or very short content
                target_score = 0.2
                rationale = "Low quality cyber content - Reddit post or minimal content"
            elif any(
                keyword in title.lower()
                for keyword in ["vulnerability", "exploit", "cve", "zero-day", "breach"]
            ):
                # High quality - actual security research/disclosures
                target_score = 0.8
                rationale = "High quality cybersecurity content - vulnerability disclosure or security research"
            elif any(
                keyword in title.lower()
                for keyword in ["tool", "framework", "analysis", "research"]
            ):
                # Medium-high quality - security tools/analysis
                target_score = 0.7
                rationale = (
                    "Good quality cybersecurity content - tools, analysis, or research"
                )
            elif content_length > 500 and any(
                keyword in content.lower()
                for keyword in ["security", "attack", "defense"]
            ):
                # Medium quality - substantial security content
                target_score = 0.6
                rationale = "Medium quality cybersecurity content with substantial technical details"
            else:
                # Low-medium quality
                target_score = 0.3
                rationale = "Low-medium quality cyber content - mentions security but lacks depth"

            article_ids.append(article_id)
            target_scores.append(target_score)
            rationales.append(rationale)

            print(f"   {title[:60]}... -> Target: {target_score}")

        # Add training data
        tuner.collect_training_data(article_ids, target_scores, rationales)

        # Show final count
        training_count = len(tuner.get_training_data())
        print(
            f"\n✅ Added cyber-specific training data. Total examples: {training_count}"
        )

        if training_count >= 5:
            print("\n🚀 Ready to run cyber-specific tuning experiment!")
            print(
                "Run: python3 scripts/tune_prompts.py tune Cyber --iterations 2 --population 3"
            )
        else:
            print(f"⚠️  Need at least 5 examples for tuning (have {training_count})")

    finally:
        tuner.close()
        mongo_client.close()


if __name__ == "__main__":
    clear_and_setup_cyber_training()
