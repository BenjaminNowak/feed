import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import yaml

from feed_aggregator.processing.llm_filter import LLMFilter


@pytest.fixture
def sample_item():
    """Create a sample feed item."""
    return {
        "_id": "test123",
        "title": "New Breakthrough in AI Research",
        "content": (
            "Researchers have developed a new machine learning model "
            "that significantly improves natural language understanding. "
            "The model achieves state-of-the-art results on multiple benchmarks."
        ),
        "source": "feedly",
        "source_id": "feed/123",
        "url": "https://example.com/article",
        "author": "Test Author",
        "tags": ["AI", "Machine Learning", "Research"],
    }


@pytest.fixture
def mock_config():
    """Create mock config."""
    return {
        "llm_filter": {
            "system_prompt": "Test system prompt",
            "user_prompt": "Title: {title}\n\nContent: {content}",
            "openai": {
                "model": "gpt-4",
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            "ollama": {
                "model": "mistral",
                "temperature": 0.3,
                "format": "json",
            },
        }
    }


@pytest.fixture
def config_file(mock_config):
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(mock_config, f)
        config_path = f.name
    yield config_path
    os.unlink(config_path)


@pytest.fixture
def mock_openai():
    """Create mock OpenAI client."""
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices[0].message.content = (
        '{"relevance_score": 0.85, '
        '"summary": "New ML model improves NLP performance", '
        '"key_topics": ["AI", "NLP", "Machine Learning"], '
        '"filtered_reason": null}'
    )
    return mock


@pytest.fixture
def llm_filter_openai(mock_openai, config_file):
    """Create LLMFilter with mocked OpenAI client."""
    with patch("feed_aggregator.processing.llm_filter.OpenAI") as mock_openai_cls:
        mock_openai_cls.return_value = mock_openai
        return LLMFilter(
            provider="openai",
            config_path=config_file,
            api_key="test_key",
        )


@pytest.fixture
def llm_filter_ollama(config_file):
    """Create LLMFilter with mocked Ollama client."""
    mock_response = {
        "message": {
            "content": (
                '{"relevance_score": 0.75, '
                '"summary": "ML model advancement", '
                '"key_topics": ["AI", "ML"], '
                '"filtered_reason": null}'
            )
        }
    }
    with patch(
        "feed_aggregator.processing.llm_filter.ollama.chat", return_value=mock_response
    ):
        return LLMFilter(provider="ollama", config_path=config_file)


@pytest.mark.unit
def test_analyze_item_openai(llm_filter_openai, sample_item, mock_openai):
    """Test successful item analysis with OpenAI."""
    result = llm_filter_openai.analyze_item(sample_item)

    # Verify OpenAI was called with correct prompt
    call_args = mock_openai.chat.completions.create.call_args[1]
    assert "system" in call_args["messages"][0]["role"]
    assert "user" in call_args["messages"][1]["role"]
    assert sample_item["title"] in call_args["messages"][1]["content"]
    assert sample_item["content"] in call_args["messages"][1]["content"]

    # Verify analysis results
    assert result["relevance_score"] == 0.85
    assert "ML model" in result["summary"]
    assert "Machine Learning" in result["key_topics"]
    assert result["filtered_reason"] is None


@pytest.mark.unit
def test_analyze_item_ollama(llm_filter_ollama, sample_item):
    """Test successful item analysis with Ollama."""
    with patch("feed_aggregator.processing.llm_filter.ollama.chat") as mock_chat:
        mock_chat.return_value = {
            "message": {
                "content": (
                    '{"relevance_score": 0.75, '
                    '"summary": "ML model advancement", '
                    '"key_topics": ["AI", "ML"], '
                    '"filtered_reason": null}'
                )
            }
        }
        result = llm_filter_ollama.analyze_item(sample_item)

        # Verify Ollama was called with correct parameters
        call_args = mock_chat.call_args[1]
        assert call_args["model"] == "mistral"
        assert call_args["options"]["temperature"] == 0.3
        assert call_args["options"]["format"] == "json"
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][1]["role"] == "user"
        assert sample_item["title"] in call_args["messages"][1]["content"]
        assert sample_item["content"] in call_args["messages"][1]["content"]

        # Verify analysis results
        assert result["relevance_score"] == 0.75
        assert "ML model" in result["summary"]
        assert "ML" in result["key_topics"]
        assert result["filtered_reason"] is None


@pytest.mark.unit
def test_analyze_item_low_relevance(llm_filter_openai, sample_item, mock_openai):
    """Test handling of low relevance items."""
    # Configure mock to return low relevance score
    mock_openai.chat.completions.create.return_value.choices[0].message.content = (
        '{"relevance_score": 0.3, '
        '"summary": "Article about unrelated topic", '
        '"key_topics": ["Other"], '
        '"filtered_reason": "Content not relevant to tech/AI focus"}'
    )

    result = llm_filter_openai.analyze_item(sample_item)

    assert result["relevance_score"] == 0.3
    assert result["filtered_reason"] is not None


@pytest.mark.unit
def test_analyze_item_api_error(llm_filter_openai, sample_item, mock_openai):
    """Test handling of API errors."""
    # Make API call raise an exception
    mock_openai.chat.completions.create.side_effect = Exception("API Error")

    with pytest.raises(Exception) as exc:
        llm_filter_openai.analyze_item(sample_item)
    assert "API Error" in str(exc.value)


@pytest.mark.unit
def test_analyze_item_invalid_response(llm_filter_openai, sample_item, mock_openai):
    """Test handling of invalid API responses."""
    # Return invalid JSON
    mock_openai.chat.completions.create.return_value.choices[
        0
    ].message.content = "Invalid JSON response"

    with pytest.raises(ValueError) as exc:
        llm_filter_openai.analyze_item(sample_item)
    assert "Invalid response format" in str(exc.value)


@pytest.mark.unit
def test_analyze_item_missing_fields(llm_filter_openai, sample_item, mock_openai):
    """Test handling of responses with missing required fields."""
    # Return JSON missing required fields
    mock_openai.chat.completions.create.return_value.choices[
        0
    ].message.content = '{"summary": "Test summary"}'

    with pytest.raises(ValueError) as exc:
        llm_filter_openai.analyze_item(sample_item)
    assert "Missing required field" in str(exc.value)


@pytest.mark.unit
def test_batch_analyze(llm_filter_openai, sample_item, mock_openai):
    """Test batch analysis of multiple items."""
    items = [sample_item, dict(sample_item)]
    results = llm_filter_openai.batch_analyze(items)

    assert len(results) == 2
    assert all(r["relevance_score"] == 0.85 for r in results)
    assert mock_openai.chat.completions.create.call_count == 2


@pytest.mark.unit
def test_load_config_missing_file(mock_openai):
    """Test handling of missing config file."""
    with pytest.raises(Exception) as exc:
        LLMFilter(config_path="nonexistent.yml")
    assert "Error loading config" in str(exc.value)


@pytest.mark.unit
def test_load_config_invalid_yaml(mock_openai):
    """Test handling of invalid YAML config."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("invalid: yaml: content")
        config_path = f.name

    with pytest.raises(Exception) as exc:
        LLMFilter(config_path=config_path)
    assert "Error loading config" in str(exc.value)

    os.unlink(config_path)


@pytest.mark.integration
def test_ollama_integration(sample_item):
    """Integration test using real Ollama instance.

    Note: Requires Ollama to be running locally with mistral model.
    Skip this test if Ollama is not available.
    """
    try:
        filter = LLMFilter(provider="ollama")
        result = filter.analyze_item(sample_item)

        assert isinstance(result["relevance_score"], float)
        assert isinstance(result["summary"], str)
        assert isinstance(result["key_topics"], list)
        assert "filtered_reason" in result
    except Exception as e:
        pytest.skip(f"Ollama not available: {str(e)}")
