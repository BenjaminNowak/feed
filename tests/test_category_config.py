"""Tests for category configuration management."""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from feed_aggregator.config.category_config import CategoryConfig


@pytest.fixture
def sample_config():
    """Sample category configuration for testing."""
    return {
        "categories": {
            "ML": {
                "name": "Machine Learning",
                "description": "ML and AI content",
                "feedly_category": "ML",
                "prompts_file": "ml.yml",
                "quality_threshold": 0.6,
                "high_quality_target": 10,
                "output_feed": "feed_ml.xml",
            },
            "Tech": {
                "name": "Technology",
                "description": "General tech content",
                "feedly_category": "Tech",
                "prompts_file": "tech.yml",
                "quality_threshold": 0.7,
                "high_quality_target": 8,
                "output_feed": "feed_tech.xml",
            },
        },
        "global": {"default_fetch_count": 100, "default_provider": "ollama"},
    }


@pytest.fixture
def temp_config_file(sample_config):
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(sample_config, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


def test_category_config_initialization(temp_config_file):
    """Test CategoryConfig initialization."""
    config = CategoryConfig(temp_config_file)
    assert config.config_path == temp_config_file
    assert "categories" in config.config
    assert "global" in config.config


def test_get_category_config(temp_config_file):
    """Test getting configuration for a specific category."""
    config = CategoryConfig(temp_config_file)

    ml_config = config.get_category_config("ML")
    assert ml_config["name"] == "Machine Learning"
    assert ml_config["quality_threshold"] == 0.6
    assert ml_config["feedly_category"] == "ML"


def test_get_category_config_not_found(temp_config_file):
    """Test error when category not found."""
    config = CategoryConfig(temp_config_file)

    with pytest.raises(ValueError, match="Category 'NonExistent' not found"):
        config.get_category_config("NonExistent")


def test_get_all_categories(temp_config_file):
    """Test getting all category keys."""
    config = CategoryConfig(temp_config_file)

    categories = config.get_all_categories()
    assert set(categories) == {"ML", "Tech"}


def test_get_global_config(temp_config_file):
    """Test getting global configuration."""
    config = CategoryConfig(temp_config_file)

    global_config = config.get_global_config()
    assert global_config["default_fetch_count"] == 100
    assert global_config["default_provider"] == "ollama"


def test_get_prompts_path(temp_config_file):
    """Test getting prompts file path."""
    config = CategoryConfig(temp_config_file)

    prompts_path = config.get_prompts_path("ML")
    expected_path = os.path.join(os.path.dirname(temp_config_file), "prompts", "ml.yml")
    assert prompts_path == expected_path


def test_get_quality_threshold(temp_config_file):
    """Test getting quality threshold."""
    config = CategoryConfig(temp_config_file)

    assert config.get_quality_threshold("ML") == 0.6
    assert config.get_quality_threshold("Tech") == 0.7


def test_get_high_quality_target(temp_config_file):
    """Test getting high quality target."""
    config = CategoryConfig(temp_config_file)

    assert config.get_high_quality_target("ML") == 10
    assert config.get_high_quality_target("Tech") == 8


def test_get_feedly_category(temp_config_file):
    """Test getting Feedly category name."""
    config = CategoryConfig(temp_config_file)

    assert config.get_feedly_category("ML") == "ML"
    assert config.get_feedly_category("Tech") == "Tech"


def test_get_output_feed(temp_config_file):
    """Test getting output feed filename."""
    config = CategoryConfig(temp_config_file)

    assert config.get_output_feed("ML") == "feed_ml.xml"
    assert config.get_output_feed("Tech") == "feed_tech.xml"


def test_get_output_feed_default(temp_config_file, sample_config):
    """Test getting output feed with default value."""
    # Remove output_feed from one category
    del sample_config["categories"]["ML"]["output_feed"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(sample_config, f)
        temp_path = f.name

    try:
        config = CategoryConfig(temp_path)
        assert config.get_output_feed("ML") == "feed.xml"  # Default value
    finally:
        os.unlink(temp_path)


def test_invalid_config_file():
    """Test error handling for invalid config file."""
    with pytest.raises(ValueError, match="Error loading category config"):
        CategoryConfig("/nonexistent/path.yml")


def test_invalid_config_format():
    """Test error handling for invalid config format."""
    invalid_config = {"invalid": "config"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(invalid_config, f)
        temp_path = f.name

    try:
        with pytest.raises(
            ValueError, match="Invalid config format: missing categories section"
        ):
            CategoryConfig(temp_path)
    finally:
        os.unlink(temp_path)


def test_default_config_path():
    """Test default config path resolution."""
    with patch("os.path.join") as mock_join:
        with patch("builtins.open", side_effect=FileNotFoundError):
            mock_join.return_value = "/expected/path/config/categories.yml"

            with pytest.raises(ValueError):
                CategoryConfig()

            # Verify the expected path was constructed
            mock_join.assert_called()
