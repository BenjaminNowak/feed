"""Unit tests for cyber category prompt tuning."""

from unittest.mock import Mock, patch

import pytest

from feed_aggregator.processing.prompt_tuner import PromptTuner


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB client."""
    with patch("feed_aggregator.storage.mongodb_client.MongoDBClient") as mock:
        client = Mock()
        # Setup mock collections
        client.db.prompt_training_data = Mock()
        client.db.prompt_tuning_experiments = Mock()
        client.db.candidate_prompts = Mock()
        client.feed_items = Mock()

        # Setup find_one to return article
        client.feed_items.find_one.return_value = {
            "id": "test_id",
            "title": "Test Article",
            "content": {"content": "Test content"},
        }

        mock.return_value = client
        yield client


@pytest.fixture
def mock_training_data():
    """Mock training data."""
    return [
        {
            "article_id": f"test{i}",
            "title": f"Test {i}",
            "content": f"Content {i}",
            "target_score": 0.8,
        }
        for i in range(10)
    ]


@pytest.fixture
def mock_llm_filter():
    """Mock LLMFilter."""
    with patch("feed_aggregator.processing.llm_filter.LLMFilter") as mock:
        llm = Mock()
        llm.analyze_item.return_value = {"relevance_score": 0.75}
        mock.return_value = llm
        yield llm


@pytest.fixture
def mock_yaml_safe_load():
    """Mock yaml.safe_load to return valid configs."""
    with patch("yaml.safe_load") as mock:

        def side_effect(arg):
            # For categories.yml
            if isinstance(arg, Mock):
                return {
                    "categories": {
                        "cyber": {
                            "name": "Cyber Security",
                            "feeds": [],
                            "prompts_file": "cyber.yml",
                        }
                    }
                }
            # For prompt config file
            return {
                "llm_filter": {
                    "system_prompt": "Base prompt for testing",
                    "version": "1.0",
                }
            }

        mock.side_effect = side_effect
        yield mock


@pytest.fixture
def tuner(mock_mongo_client, mock_yaml_safe_load):
    """Create PromptTuner instance with mocked dependencies."""
    with patch("builtins.open", create=True) as mock_open:
        # Mock file reads
        mock_open.return_value.__enter__.return_value = Mock()
        tuner = PromptTuner("cyber")
        yield tuner


@pytest.mark.skip(reason="Prompt tuning feature in backlog")
def test_collect_training_data(tuner, mock_mongo_client):
    """Test collecting training data."""
    # Add training data
    tuner.collect_training_data(
        article_ids=["test_id"],
        target_scores=[0.8],
        rationales=["Good cybersecurity article"],
    )

    # Verify data was stored
    mock_mongo_client.db.prompt_training_data.insert_many.assert_called_once()
    stored_data = mock_mongo_client.db.prompt_training_data.insert_many.call_args[0][0]

    assert len(stored_data) == 1
    record = stored_data[0]
    assert record["article_id"] == "test_id"
    assert record["title"] == "Test Article"
    assert record["content"] == "Test content"
    assert record["target_score"] == 0.8
    assert record["category"] == "cyber"
    assert record["human_rationale"] == "Good cybersecurity article"


@pytest.mark.skip(reason="Prompt tuning feature in backlog")
def test_evaluate_prompt(tuner, mock_llm_filter):
    """Test prompt evaluation."""
    test_data = [
        {
            "article_id": "test1",
            "title": "Test 1",
            "content": "Content 1",
            "target_score": 0.8,
        },
        {
            "article_id": "test2",
            "title": "Test 2",
            "content": "Content 2",
            "target_score": 0.7,
        },
    ]

    metrics = tuner.evaluate_prompt(
        prompt_config={"system_prompt": "Test prompt"}, test_data=test_data
    )

    assert "mse" in metrics
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "accuracy" in metrics
    assert metrics["num_predictions"] == 2

    # With our mock returning 0.75 for all predictions:
    assert metrics["mae"] == pytest.approx(0.075)  # |0.75-0.8| + |0.75-0.7| / 2


@pytest.mark.skip(reason="Prompt tuning feature in backlog")
def test_generate_prompt_variations(tuner, mock_llm_filter):
    """Test generating prompt variations."""
    mock_llm_filter._analyze_with_ollama.return_value = {
        "summary": "VARIATION 1: Test variation 1\nVARIATION 2: Test variation 2"
    }

    variations = tuner.generate_prompt_variations(
        base_prompt="Base prompt", num_variations=2
    )

    assert len(variations) == 2
    assert variations[0] == "Test variation 1"
    assert variations[1] == "Test variation 2"


@pytest.mark.skip(reason="Prompt tuning feature in backlog")
def test_tune_prompts(tuner, mock_mongo_client, mock_llm_filter, mock_training_data):
    """Test full prompt tuning workflow."""
    # Mock training data
    mock_mongo_client.db.prompt_training_data.find.return_value = mock_training_data

    # Run tuning
    experiment = tuner.tune_prompts(max_iterations=2, population_size=3)

    assert "iterations" in experiment
    assert len(experiment["iterations"]) == 2
    assert "final_config" in experiment
    assert "improvement" in experiment

    # Verify experiment was stored
    mock_mongo_client.db.prompt_tuning_experiments.insert_one.assert_called_once()


@pytest.mark.skip(reason="Prompt tuning feature in backlog")
def test_apply_best_prompt(tuner, mock_mongo_client):
    """Test applying the best prompt from an experiment."""
    experiment_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format

    # Mock experiment data
    mock_mongo_client.db.prompt_tuning_experiments.find_one.return_value = {
        "_id": experiment_id,
        "final_config": {"system_prompt": "Best prompt", "version": "1.0"},
    }

    success = tuner.apply_best_prompt(experiment_id)
    assert success is True
