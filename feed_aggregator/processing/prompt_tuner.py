"""
Automated Prompt Tuning System

This system uses MongoDB training data to automatically optimize LLM prompts
for better relevance scoring accuracy.
"""

import logging
import math
import random
from datetime import UTC, datetime
from typing import Dict, List, Optional

import yaml

from feed_aggregator.config.category_config import CategoryConfig
from feed_aggregator.processing.llm_filter import LLMFilter
from feed_aggregator.storage.mongodb_client import MongoDBClient

logger = logging.getLogger(__name__)


class PromptTuner:  # pragma: no cover
    """Automated prompt tuning system using evolutionary optimization."""

    def __init__(self, category: str, provider: str = "ollama"):  # pragma: no cover
        """Initialize prompt tuner.

        Args:
            category: Category to tune prompts for
            provider: LLM provider to use
        """
        self.category = category
        self.provider = provider
        self.category_config = CategoryConfig()
        self.mongo_client = MongoDBClient()

        # Collections for tuning data
        self.training_data = self.mongo_client.db.prompt_training_data
        self.tuning_experiments = self.mongo_client.db.prompt_tuning_experiments
        self.candidate_prompts = self.mongo_client.db.candidate_prompts

        # Load current prompt configuration
        self.current_config_path = self.category_config.get_prompts_path(category)
        with open(self.current_config_path, "r") as f:
            self.base_config = yaml.safe_load(f)

    def collect_training_data(  # pragma: no cover
        self, article_ids: List[str], target_scores: List[float], rationales: List[str]
    ) -> None:
        """Collect training data from existing articles.

        Args:
            article_ids: List of MongoDB article IDs
            target_scores: Target relevance scores (0.0-1.0)
            rationales: Human rationale for each score
        """
        training_records = []

        for article_id, target_score, rationale in zip(
            article_ids, target_scores, rationales
        ):
            # Get article from MongoDB
            article = self.mongo_client.feed_items.find_one({"id": article_id})
            if not article:
                logger.warning(f"Article {article_id} not found")
                continue

            # Extract content
            content = ""
            if "content" in article and "content" in article["content"]:
                content = article["content"]["content"]
            elif "summary" in article and "content" in article["summary"]:
                content = article["summary"]["content"]

            training_record = {
                "article_id": article_id,
                "title": article.get("title", ""),
                "content": content,
                "target_score": target_score,
                "category": self.category,
                "human_rationale": rationale,
                "created_at": datetime.now(UTC),
                "content_length": len(content),
                "word_count": len(content.split()) if content else 0,
            }

            training_records.append(training_record)

        # Store in MongoDB
        if training_records:
            self.training_data.insert_many(training_records)
            logger.info(
                f"Added {len(training_records)} training records for {self.category}"
            )

    def get_training_data(
        self, limit: Optional[int] = None
    ) -> List[Dict]:  # pragma: no cover
        """Get training data for the category.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of training records
        """
        query = {"category": self.category}
        cursor = self.training_data.find(query)

        if limit:
            cursor = cursor.limit(limit)

        return list(cursor)

    def evaluate_prompt(
        self, prompt_config: Dict, test_data: List[Dict]
    ) -> Dict:  # pragma: no cover
        """Evaluate a prompt configuration against test data.

        Args:
            prompt_config: Prompt configuration to test
            test_data: List of test records with target scores

        Returns:
            Evaluation metrics
        """
        # Create temporary config file using secure method
        import tempfile

        temp_file = tempfile.NamedTemporaryFile(
            prefix=f"prompt_{self.category}_", suffix=".yml", delete=False
        )
        temp_config_path = temp_file.name
        temp_file.close()
        with open(temp_config_path, "w") as f:
            yaml.dump({"llm_filter": prompt_config}, f)

        try:
            # Initialize LLM filter with test prompt
            llm_filter = LLMFilter(provider=self.provider, config_path=temp_config_path)

            predictions = []
            targets = []
            errors = []

            for record in test_data:
                try:
                    # Get prediction
                    result = llm_filter.analyze_item(
                        {"title": record["title"], "content": record["content"]}
                    )

                    predicted_score = result["relevance_score"]
                    target_score = record["target_score"]

                    predictions.append(predicted_score)
                    targets.append(target_score)
                    errors.append(abs(predicted_score - target_score))

                except (KeyError, ValueError, RuntimeError) as e:
                    logger.error(f"Error evaluating record {record['article_id']}: {e}")
                    continue

            if not predictions:
                return {"error": "No successful predictions"}

            # Calculate metrics
            mse = sum((p - t) ** 2 for p, t in zip(predictions, targets)) / len(
                predictions
            )
            mae = sum(errors) / len(errors)
            rmse = math.sqrt(mse)

            # Classification accuracy (within 0.1 threshold)
            correct_classifications = sum(1 for e in errors if e <= 0.1)
            accuracy = correct_classifications / len(errors)

            return {
                "mse": mse,
                "mae": mae,
                "rmse": rmse,
                "accuracy": accuracy,
                "num_predictions": len(predictions),
                "predictions": predictions,
                "targets": targets,
                "errors": errors,
            }

        finally:
            # Clean up temp file
            import os

            if os.path.exists(temp_config_path):
                os.unlink(temp_config_path)

    def store_candidate_prompt(  # pragma: no cover
        self,
        experiment_id: str,
        iteration: int,
        prompt_version: str,
        config: Dict,
        metrics: Dict,
    ) -> str:
        """Store a candidate prompt in MongoDB.

        Args:
            experiment_id: ID of the tuning experiment
            iteration: Iteration number
            prompt_version: Version identifier for this prompt
            config: Full prompt configuration
            metrics: Evaluation metrics

        Returns:
            MongoDB ID of the stored candidate prompt
        """
        candidate = {
            "experiment_id": experiment_id,
            "category": self.category,
            "iteration": iteration,
            "prompt_version": prompt_version,
            "config": config,
            "metrics": metrics,
            "created_at": datetime.now(UTC),
            "provider": self.provider,
        }

        result = self.candidate_prompts.insert_one(candidate)
        return str(result.inserted_id)

    def generate_prompt_variations(  # pragma: no cover
        self, base_prompt: str, num_variations: int = 5
    ) -> List[str]:
        """Generate prompt variations using LLM.

        Args:
            base_prompt: Base system prompt to vary
            num_variations: Number of variations to generate

        Returns:
            List of prompt variations
        """
        # Use LLM to generate variations
        variation_prompt = f"""
        You are a prompt engineering expert. Given the following system prompt for content relevance scoring,
        generate {num_variations} improved variations that might perform better.

        Focus on:
        1. Clearer criteria definitions
        2. Better examples of high/medium/low relevance
        3. More specific technical requirements
        4. Better handling of edge cases

        Original prompt:
        {base_prompt}

        Return only the variations, one per line, starting with "VARIATION N:".
        """

        # Create a simple LLM filter for prompt generation
        temp_filter = LLMFilter(provider=self.provider, category=self.category)

        try:
            # This is a bit meta - using the LLM to improve its own prompts
            result = temp_filter._analyze_with_ollama(
                "You are a prompt engineering expert.", variation_prompt
            )

            # Parse variations from response
            variations = []
            lines = result.get("summary", "").split("\n")
            for line in lines:
                if line.strip().startswith("VARIATION"):
                    variation = line.split(":", 1)[1].strip()
                    if variation:
                        variations.append(variation)

            return variations[:num_variations]

        except Exception as e:
            logger.error(f"Error generating prompt variations: {e}")
            return []

    def tune_prompts(
        self, max_iterations: int = 10, population_size: int = 8
    ) -> Dict:  # pragma: no cover
        """Run automated prompt tuning experiment.

        Args:
            max_iterations: Maximum number of tuning iterations
            population_size: Number of prompt variations to test per iteration

        Returns:
            Best prompt configuration and results
        """
        # Get training data
        training_data = self.get_training_data()
        if len(training_data) < 5:
            raise ValueError(
                f"Need at least 5 training examples, got {len(training_data)}"
            )

        # Split into train/test
        random.shuffle(training_data)
        split_idx = int(0.8 * len(training_data))
        train_data = training_data[:split_idx]
        test_data = training_data[split_idx:]

        logger.info(
            f"Training on {len(train_data)} examples, testing on {len(test_data)}"
        )

        # Initialize experiment tracking
        experiment = {
            "category": self.category,
            "provider": self.provider,
            "started_at": datetime.now(UTC),
            "max_iterations": max_iterations,
            "population_size": population_size,
            "training_size": len(train_data),
            "test_size": len(test_data),
            "iterations": [],
        }

        # Start with base prompt
        current_best_config = self.base_config["llm_filter"].copy()
        current_best_score = float("inf")  # We want to minimize error

        # Evaluate baseline
        baseline_metrics = self.evaluate_prompt(current_best_config, test_data)
        logger.info(
            f"Baseline performance: MAE={baseline_metrics.get('mae', 'N/A'):.3f}"
        )

        for iteration in range(max_iterations):
            logger.info(f"Starting iteration {iteration + 1}/{max_iterations}")

            # Generate prompt variations
            base_system_prompt = current_best_config["system_prompt"]
            variations = self.generate_prompt_variations(
                base_system_prompt, population_size - 1
            )

            # Test all variations
            iteration_results = []

            # Include current best in population
            test_configs = [current_best_config]

            # Add variations
            for i, variation in enumerate(variations):
                variant_config = current_best_config.copy()
                variant_config["system_prompt"] = variation
                variant_config[
                    "version"
                ] = f"{current_best_config.get('version', '1.0')}_var{i+1}"
                test_configs.append(variant_config)

            # Evaluate each configuration
            for j, config in enumerate(test_configs):
                logger.info(f"Evaluating configuration {j+1}/{len(test_configs)}")
                metrics = self.evaluate_prompt(config, train_data)

                if "error" not in metrics:
                    result = {
                        "config_index": j,
                        "is_baseline": j == 0,
                        "metrics": metrics,
                        "config": config,
                    }
                    iteration_results.append(result)

            if not iteration_results:
                logger.warning(f"No valid results in iteration {iteration + 1}")
                continue

            # Find best configuration this iteration
            best_result = min(iteration_results, key=lambda x: x["metrics"]["mae"])

            # Update global best if improved
            if best_result["metrics"]["mae"] < current_best_score:
                current_best_config = best_result["config"]
                current_best_score = best_result["metrics"]["mae"]
                logger.info(f"New best MAE: {current_best_score:.3f}")
            else:
                logger.info(
                    f"No improvement this iteration (best: {current_best_score:.3f})"
                )

            # Record iteration
            experiment["iterations"].append(
                {
                    "iteration": iteration + 1,
                    "results": iteration_results,
                    "best_mae": best_result["metrics"]["mae"],
                    "global_best_mae": current_best_score,
                }
            )

        # Final evaluation on test set
        final_metrics = self.evaluate_prompt(current_best_config, test_data)

        experiment.update(
            {
                "completed_at": datetime.now(UTC),
                "final_config": current_best_config,
                "final_test_metrics": final_metrics,
                "baseline_metrics": baseline_metrics,
                "improvement": baseline_metrics.get("mae", 0)
                - final_metrics.get("mae", 0),
            }
        )

        # Store experiment in MongoDB
        experiment_result = self.tuning_experiments.insert_one(experiment)
        experiment_id = str(experiment_result.inserted_id)

        # Store all candidate prompts from the experiment
        for iteration_data in experiment["iterations"]:
            iteration_num = iteration_data["iteration"]
            for result in iteration_data["results"]:
                prompt_version = result["config"].get(
                    "version", f"baseline_iter{iteration_num}"
                )
                self.store_candidate_prompt(
                    experiment_id=experiment_id,
                    iteration=iteration_num,
                    prompt_version=prompt_version,
                    config=result["config"],
                    metrics=result["metrics"],
                )

        logger.info(
            f"Tuning completed. Final MAE: {final_metrics.get('mae', 'N/A'):.3f}"
        )
        logger.info(f"Improvement over baseline: {experiment['improvement']:.3f}")
        logger.info(
            f"Stored {sum(len(iter_data['results']) for iter_data in experiment['iterations'])} candidate prompts"
        )

        # Add experiment ID to the returned experiment
        experiment["_id"] = experiment_result.inserted_id
        return experiment

    def apply_best_prompt(self, experiment_id: str) -> bool:  # pragma: no cover
        """Apply the best prompt from a tuning experiment.

        Args:
            experiment_id: MongoDB ID of the experiment

        Returns:
            True if successfully applied
        """
        from bson import ObjectId

        experiment = self.tuning_experiments.find_one({"_id": ObjectId(experiment_id)})
        if not experiment:
            logger.error(f"Experiment {experiment_id} not found")
            return False

        best_config = experiment["final_config"]

        # Update version number
        current_version = best_config.get("version", "1.0")
        if "_var" in current_version:
            base_version = current_version.split("_var")[0]
        else:
            base_version = current_version

        # Increment version
        try:
            major, minor = base_version.split(".")
            new_version = f"{major}.{int(minor) + 1}"
        except ValueError:
            new_version = "2.0"

        best_config["version"] = new_version

        # Write to config file
        full_config = {"llm_filter": best_config}
        with open(self.current_config_path, "w") as f:
            yaml.dump(full_config, f, default_flow_style=False)

        logger.info(f"Applied tuned prompt version {new_version} for {self.category}")
        return True

    def close(self):  # pragma: no cover
        """Close database connections."""
        self.mongo_client.close()
