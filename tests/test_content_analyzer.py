import pytest

from feed_aggregator.processing.content_analyzer import ContentAnalyzer


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
        "llm_analysis": {
            "relevance_score": 0.85,
            "summary": "New ML model improves NLP performance",
            "key_topics": ["AI", "NLP", "Machine Learning"],
            "filtered_reason": None,
        },
    }


@pytest.mark.skip(reason="Content analyzer being re-evaluated - Feedly provides topics")
@pytest.mark.unit
def test_extract_technical_terms():
    """Test extraction of technical terms and version numbers."""
    analyzer = ContentAnalyzer()
    text = (
        "The GPT-4 and BERT models are popular in NLP. Python3 developers "
        "use PyTorch 2.0 for deep learning tasks. The T5-base model shows "
        "promise in text-to-text tasks."
    )

    keywords = analyzer.extract_keywords(text)

    # Test technical terms with version numbers
    assert "GPT-4" in keywords
    assert "Python3" in keywords
    assert "PyTorch 2.0" in keywords
    assert "T5-base" in keywords

    # Test acronyms
    assert "NLP" in keywords
    assert "BERT" in keywords


@pytest.mark.unit
def test_extract_multi_word_phrases():
    """Test extraction of multi-word technical phrases."""
    analyzer = ContentAnalyzer()
    text = (
        "Natural language processing has evolved significantly. "
        "Machine learning models use deep neural networks for "
        "complex pattern recognition tasks. The transformer architecture "
        "enables better contextual understanding."
    )

    keywords = analyzer.extract_keywords(text)

    # Test multi-word technical phrases
    assert "natural language processing" in keywords
    assert "machine learning" in keywords
    assert "neural networks" in keywords
    assert "pattern recognition" in keywords
    assert "transformer architecture" in keywords


@pytest.mark.skip(reason="Content analyzer being re-evaluated - Feedly provides topics")
@pytest.mark.unit
def test_extract_named_entities():
    """Test named entity recognition."""
    analyzer = ContentAnalyzer()
    text = (
        "Google researchers at DeepMind published a paper with Microsoft "
        "and OpenAI scientists. The study was conducted at Stanford University "
        "and presented at the NeurIPS conference."
    )

    keywords = analyzer.extract_keywords(text)

    # Test organization names
    assert "Google" in keywords
    assert "DeepMind" in keywords
    assert "Microsoft" in keywords
    assert "OpenAI" in keywords
    assert "Stanford University" in keywords
    assert "NeurIPS" in keywords


@pytest.mark.unit
def test_extract_complex_technical_phrases():
    """Test extraction of complex technical phrases with prepositions."""
    analyzer = ContentAnalyzer()
    text = (
        "State of the art results in computer vision show promise. "
        "The principle of least privilege in security is crucial. "
        "Quality of service in networking requires optimization. "
        "The theory of computation guides algorithm design."
    )

    keywords = analyzer.extract_keywords(text)

    # Test complex phrases
    assert "state of the art" in keywords
    assert "computer vision" in keywords
    assert "principle of least privilege" in keywords
    assert "quality of service" in keywords
    assert "theory of computation" in keywords


@pytest.mark.unit
def test_analyze_readability():
    """Test readability analysis."""
    analyzer = ContentAnalyzer()
    text = (
        "The model uses attention mechanisms. It processes text efficiently. "
        "The architecture is complex but well-designed. Results are strong."
    )

    metrics = analyzer.analyze_readability(text)

    assert "flesch_score" in metrics
    assert "avg_sentence_length" in metrics
    assert "avg_word_length" in metrics
    assert isinstance(metrics["flesch_score"], float)
    assert isinstance(metrics["avg_sentence_length"], float)
    assert isinstance(metrics["avg_word_length"], float)


@pytest.mark.unit
def test_analyze_item(sample_item):
    """Test full item analysis."""
    analyzer = ContentAnalyzer()
    result = analyzer.analyze_item(sample_item)

    assert "keywords" in result
    assert "readability" in result
    assert "word_count" in result
    assert "sentence_count" in result
    assert "reading_time_minutes" in result
    assert isinstance(result["keywords"], list)
    assert isinstance(result["readability"], dict)
    assert isinstance(result["word_count"], int)
    assert isinstance(result["sentence_count"], int)
    assert isinstance(result["reading_time_minutes"], float)


@pytest.mark.unit
def test_analyze_item_empty_content():
    """Test analysis of item with empty content."""
    analyzer = ContentAnalyzer()
    empty_item = {
        "title": "Test",
        "content": "",
        "llm_analysis": {"summary": "Empty test"},
    }

    result = analyzer.analyze_item(empty_item)

    assert result["word_count"] == 0
    assert result["sentence_count"] == 0
    assert result["reading_time_minutes"] == 0
    assert len(result["keywords"]) == 0


@pytest.mark.unit
def test_analyze_item_missing_fields():
    """Test handling of missing fields."""
    analyzer = ContentAnalyzer()
    invalid_item = {"title": "Test"}

    with pytest.raises(ValueError) as exc:
        analyzer.analyze_item(invalid_item)
    assert "Missing required field" in str(exc.value)


@pytest.mark.unit
def test_batch_analyze():
    """Test batch analysis of multiple items."""
    analyzer = ContentAnalyzer()
    items = [
        {
            "title": "Test 1",
            "content": "Short test content one.",
            "llm_analysis": {"summary": "Test 1"},
        },
        {
            "title": "Test 2",
            "content": "Short test content two.",
            "llm_analysis": {"summary": "Test 2"},
        },
    ]

    results = analyzer.batch_analyze(items)

    assert len(results) == 2
    assert all("keywords" in r for r in results)
    assert all("readability" in r for r in results)
    assert all("word_count" in r for r in results)
