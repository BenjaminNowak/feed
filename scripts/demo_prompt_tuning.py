#!/usr/bin/env python3
"""
Demo script showing how to use the automated prompt tuning system.

This creates some sample training data and shows how the system works.
"""

import logging

from feed_aggregator.processing.prompt_tuner import PromptTuner

logging.basicConfig(level=logging.INFO)


def main():
    print("🔧 Automated Prompt Tuning System Demo")
    print("=" * 50)

    # Example: Add training data for the published article that got 0.85 but should be lower
    article_id = (  # noqa: E501
        "Bv5TdBWfcWFbQc0onABBZ1VLqSAA/Kz8RimFcz+sMHM=_1976e6c6239:2ff75cc:c6e49d22"
    )

    print(f"📝 Adding training data for article: {article_id}")
    print("   This is the Reddit post that got 0.85 but should be lower")

    tuner = PromptTuner("Tech", "ollama")

    try:
        # Add training data - this Reddit post should get a low score
        tuner.collect_training_data(
            article_ids=[article_id],
            target_scores=[0.3],  # Should be low-medium, not high
            rationales=[
                "Reddit post with just links to external content, lacks substantial technical analysis in the post itself"  # noqa: E501
            ],
        )

        print("✅ Training data added")

        # Show current training data
        training_data = tuner.get_training_data()
        print(f"📊 Total training examples for Tech: {len(training_data)}")

        if len(training_data) >= 5:
            print("\n🚀 Running mini tuning experiment...")

            # Run a small tuning experiment
            experiment = tuner.tune_prompts(max_iterations=2, population_size=3)

            print("\n🎯 Results:")
            print(
                f"   Baseline MAE: {experiment['baseline_metrics'].get('mae', 'N/A'):.3f}"
            )
            print(
                f"   Final MAE: {experiment['final_test_metrics'].get('mae', 'N/A'):.3f}"
            )
            print(f"   Improvement: {experiment.get('improvement', 0):.3f}")
            print(f"   Experiment ID: {experiment['_id']}")

        else:
            print(
                f"⚠️  Need at least 5 training examples to run tuning "
                f"(have {len(training_data)})"
            )
            print("   Add more examples using:")
            print(
                "   python3 scripts/tune_prompts.py add-training Tech "
                "--articles 'id1,id2' --scores '0.2,0.8' "
                "--rationales 'reason1,reason2'"
            )

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        tuner.close()

    print("\n📚 Usage Examples:")
    print("   # Add more training data:")
    print("   python3 scripts/tune_prompts.py add-training Tech \\")
    print("     --articles 'article_id_1,article_id_2' \\")
    print("     --scores '0.2,0.8' \\")
    print("     --rationales 'Low quality post,High quality analysis'")
    print()
    print("   # Run full tuning:")
    print("   python3 scripts/tune_prompts.py tune Tech --iterations 10 --population 8")
    print()
    print("   # Apply best prompt:")
    print(
        "   python3 scripts/tune_prompts.py apply Tech --experiment-id <experiment_id>"
    )


if __name__ == "__main__":
    main()
