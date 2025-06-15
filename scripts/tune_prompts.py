#!/usr/bin/env python3
"""
Command-line interface for automated prompt tuning.

Usage examples:
  # Add training data
  python3 scripts/tune_prompts.py add-training Tech \
    --articles "article_id_1,article_id_2" \
    --scores "0.2,0.8" \
    --rationales "Low quality Reddit post,High quality technical analysis"

  # Run tuning experiment
  python3 scripts/tune_prompts.py tune Tech --iterations 5 --population 6

  # Apply best prompt from experiment
  python3 scripts/tune_prompts.py apply Tech --experiment-id 507f1f77bcf86cd799439011
"""

import argparse
import logging
import sys

from feed_aggregator.processing.prompt_tuner import PromptTuner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_training_data(args):
    """Add training data for prompt tuning."""
    tuner = PromptTuner(args.category, args.provider)

    try:
        # Parse input data
        article_ids = [id.strip() for id in args.articles.split(",")]
        scores = [float(score.strip()) for score in args.scores.split(",")]
        rationales = [r.strip() for r in args.rationales.split(",")]

        if len(article_ids) != len(scores) or len(scores) != len(rationales):
            raise ValueError("Number of articles, scores, and rationales must match")

        # Validate scores
        for score in scores:
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Score {score} must be between 0.0 and 1.0")

        # Add training data
        tuner.collect_training_data(article_ids, scores, rationales)

        print(f"✅ Added {len(article_ids)} training examples for {args.category}")

        # Show current training data count
        total_training = len(tuner.get_training_data())
        print(f"📊 Total training examples for {args.category}: {total_training}")

    finally:
        tuner.close()


def run_tuning(args):
    """Run prompt tuning experiment."""
    tuner = PromptTuner(args.category, args.provider)

    try:
        # Check if we have enough training data
        training_data = tuner.get_training_data()
        if len(training_data) < 5:
            print(f"❌ Need at least 5 training examples, found {len(training_data)}")
            print("Add more training data first using: tune_prompts.py add-training")
            return

        print(f"🚀 Starting prompt tuning for {args.category}")
        print(f"📊 Training data: {len(training_data)} examples")
        print(
            f"⚙️  Parameters: {args.iterations} iterations, "
            f"{args.population} population size"
        )
        print()

        # Run tuning
        experiment = tuner.tune_prompts(
            max_iterations=args.iterations, population_size=args.population
        )

        # Show results
        print("\n" + "=" * 60)
        print("🎯 TUNING RESULTS")
        print("=" * 60)

        baseline_mae = experiment["baseline_metrics"].get("mae", 0)
        final_mae = experiment["final_test_metrics"].get("mae", 0)
        improvement = experiment.get("improvement", 0)

        print(f"Baseline MAE:     {baseline_mae:.3f}")
        print(f"Final MAE:        {final_mae:.3f}")
        print(f"Improvement:      {improvement:.3f}")
        print(f"Experiment ID:    {experiment['_id']}")

        if improvement > 0:
            print("✅ Prompt tuning improved performance!")
            print(
                f"💡 To apply the best prompt: tune_prompts.py apply {args.category} "
                f"--experiment-id {experiment['_id']}"
            )
        else:
            print("⚠️  No improvement found. Consider:")
            print("   - Adding more diverse training examples")
            print("   - Increasing iterations or population size")
            print("   - Reviewing training data quality")

    finally:
        tuner.close()


def apply_prompt(args):
    """Apply the best prompt from a tuning experiment."""
    tuner = PromptTuner(args.category, args.provider)

    try:
        success = tuner.apply_best_prompt(args.experiment_id)

        if success:
            print(f"✅ Applied tuned prompt for {args.category}")
            print("🔄 Restart any running processes to use the new prompt")
        else:
            print(
                f"❌ Failed to apply prompt. Check experiment ID: {args.experiment_id}"
            )

    finally:
        tuner.close()


def list_training_data(args):
    """List training data for a category."""
    tuner = PromptTuner(args.category, args.provider)

    try:
        training_data = tuner.get_training_data()

        print(f"📊 Training data for {args.category}: {len(training_data)} examples")
        print()

        for i, record in enumerate(training_data, 1):
            print(f"{i}. {record['title'][:50]}...")
            print(f"   Target Score: {record['target_score']}")
            print(f"   Content Length: {record['content_length']} chars")
            print(f"   Rationale: {record['human_rationale'][:100]}...")
            print()

    finally:
        tuner.close()


def main():
    parser = argparse.ArgumentParser(description="Automated prompt tuning system")
    parser.add_argument(
        "--provider",
        default="ollama",
        choices=["ollama", "openai"],
        help="LLM provider to use",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add training data command
    add_parser = subparsers.add_parser("add-training", help="Add training data")
    add_parser.add_argument("category", help="Category to add training data for")
    add_parser.add_argument(
        "--articles", required=True, help="Comma-separated list of article IDs"
    )
    add_parser.add_argument(
        "--scores",
        required=True,
        help="Comma-separated list of target scores (0.0-1.0)",
    )
    add_parser.add_argument(
        "--rationales", required=True, help="Comma-separated list of rationales"
    )

    # Tune prompts command
    tune_parser = subparsers.add_parser("tune", help="Run prompt tuning")
    tune_parser.add_argument("category", help="Category to tune prompts for")
    tune_parser.add_argument(
        "--iterations", type=int, default=5, help="Number of tuning iterations"
    )
    tune_parser.add_argument(
        "--population", type=int, default=6, help="Population size per iteration"
    )

    # Apply prompt command
    apply_parser = subparsers.add_parser("apply", help="Apply tuned prompt")
    apply_parser.add_argument("category", help="Category to apply prompt for")
    apply_parser.add_argument(
        "--experiment-id", required=True, help="Experiment ID from tuning run"
    )

    # List training data command
    list_parser = subparsers.add_parser("list-training", help="List training data")
    list_parser.add_argument("category", help="Category to list training data for")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "add-training":
            add_training_data(args)
        elif args.command == "tune":
            run_tuning(args)
        elif args.command == "apply":
            apply_prompt(args)
        elif args.command == "list-training":
            list_training_data(args)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
