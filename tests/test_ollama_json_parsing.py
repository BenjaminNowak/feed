import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from feed_aggregator.processing.llm_filter import LLMFilter


@pytest.fixture
def tech_config():
    """Create tech category config."""
    return {
        "llm_filter": {
            "version": "1.0",
            "system_prompt": (
                "You are an AI content analyzer focused on practical and "
                "substantive general technology content."
            ),
            "user_prompt": "Title: {title}\n\nContent: {content}\n\nAnalyze this content and return a JSON response.",
            "ollama": {"model": "qwen3:32b", "temperature": 0.1, "format": "json"},
        }
    }


@pytest.fixture
def tech_config_file(tech_config):
    """Create temporary tech config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(tech_config, f)
        config_path = f.name
    yield config_path
    os.unlink(config_path)


@pytest.fixture
def sample_tech_item():
    """Create a sample tech feed item."""
    return {
        "_id": "tech123",
        "title": "AMD's New GPU Architecture",
        "content": (
            "AMD has announced their new GPU architecture with flexible I/O lanes. "
            "The engineering complexity involves RCCL's reliance on NCCL fork which "
            "limits multi-node performance. Meta shows hesitation to adopt AMD NICs."
        ),
    }


def test_ollama_json_parsing_with_extra_content_fixed(
    tech_config_file, sample_tech_item
):
    """Test that the fixed JSON parsing handles extra content correctly."""

    # Simulate response with proper fields but extra content after JSON
    response_with_extra_content = {
        "message": {
            "content": """{
    "relevance_score": 0.8,
    "summary": "AMD GPU architecture discussion with challenges and opportunities",
    "key_topics": ["AMD", "GPU", "Architecture", "I/O lanes", "RCCL", "NCCL"],
    "filtered_reason": null
}

This is some additional explanation text that the model added after the JSON.
It should be ignored by the improved parsing logic."""
        }
    }

    with patch("feed_aggregator.processing.llm_filter.ollama.chat") as mock_chat:
        mock_chat.return_value = response_with_extra_content

        llm_filter = LLMFilter(provider="ollama", config_path=tech_config_file)

        # This should now work with the improved JSON extraction
        result = llm_filter.analyze_item(sample_tech_item)

        assert result["relevance_score"] == 0.8
        assert "AMD GPU architecture" in result["summary"]
        assert "AMD" in result["key_topics"]
        assert result["filtered_reason"] is None


def test_ollama_json_parsing_with_original_error_format(
    tech_config_file, sample_tech_item
):
    """Test the original error case - wrong JSON structure with extra content."""

    # This is the exact problematic response from the user's error
    problematic_response = {
        "message": {
            "content": """{
    "challenges": [
      "Engineering complexity of flexible I/O lanes",
      "RCCL's reliance on NCCL fork limiting multi-node performance",
      "Meta's hesitation to adopt AMD NICs"
    ],
    "opportunities": [
      "Flexible I/O enabling diverse rack-scale and SSD/NIC integration",
      "Partnerships with Oracle and cloud providers",
      "Potential to address AI engineer compensation and retain talent"
    ]
  }
}
Additional text after the JSON that causes parsing to fail."""
        }
    }

    with patch("feed_aggregator.processing.llm_filter.ollama.chat") as mock_chat:
        mock_chat.return_value = problematic_response

        llm_filter = LLMFilter(provider="ollama", config_path=tech_config_file)

        # This should now fail with missing required fields, not JSON parsing error
        with pytest.raises(ValueError) as exc_info:
            llm_filter.analyze_item(sample_tech_item)

        error_msg = str(exc_info.value)
        # Should now fail on missing required fields, not JSON parsing
        assert "Missing required field" in error_msg
        assert "relevance_score" in error_msg


def test_ollama_json_parsing_with_markdown_blocks(tech_config_file, sample_tech_item):
    """Test parsing JSON response wrapped in markdown code blocks."""

    markdown_response = {
        "message": {
            "content": """```json
{
    "relevance_score": 0.8,
    "summary": "AMD GPU architecture discussion",
    "key_topics": ["AMD", "GPU", "Architecture"],
    "filtered_reason": null
}
```

This is some additional explanation text."""
        }
    }

    with patch("feed_aggregator.processing.llm_filter.ollama.chat") as mock_chat:
        mock_chat.return_value = markdown_response

        llm_filter = LLMFilter(provider="ollama", config_path=tech_config_file)

        # This should now work with the improved JSON extraction that handles markdown
        result = llm_filter.analyze_item(sample_tech_item)

        assert result["relevance_score"] == 0.8
        assert result["summary"] == "AMD GPU architecture discussion"
        assert result["key_topics"] == ["AMD", "GPU", "Architecture"]
        assert result["filtered_reason"] is None


def test_ollama_json_parsing_clean_response(tech_config_file, sample_tech_item):
    """Test parsing clean JSON response without extra content."""

    clean_response = {
        "message": {
            "content": """{
    "relevance_score": 0.8,
    "summary": "AMD GPU architecture discussion",
    "key_topics": ["AMD", "GPU", "Architecture"],
    "filtered_reason": null
}"""
        }
    }

    with patch("feed_aggregator.processing.llm_filter.ollama.chat") as mock_chat:
        mock_chat.return_value = clean_response

        llm_filter = LLMFilter(provider="ollama", config_path=tech_config_file)

        # This should work fine
        result = llm_filter.analyze_item(sample_tech_item)

        assert result["relevance_score"] == 0.8
        assert result["summary"] == "AMD GPU architecture discussion"
        assert result["key_topics"] == ["AMD", "GPU", "Architecture"]
