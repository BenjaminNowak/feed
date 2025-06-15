import pytest

from feed_aggregator.processing.llm_filter import LLMFilter


class TestJSONExtraction:
    """Test the JSON extraction method directly."""

    def setup_method(self):
        """Set up test instance."""
        self.llm_filter = LLMFilter.__new__(LLMFilter)  # Create without __init__

    def test_extract_simple_json(self):
        """Test extracting simple JSON."""
        content = '{"key": "value"}'
        result = self.llm_filter._extract_json_from_content(content)
        assert result == '{"key": "value"}'

    def test_extract_json_with_extra_content_after(self):
        """Test extracting JSON with extra content after."""
        content = '{"key": "value"}\nExtra text here'
        result = self.llm_filter._extract_json_from_content(content)
        assert result == '{"key": "value"}'

    def test_extract_json_with_extra_content_before(self):
        """Test extracting JSON with extra content before."""
        content = 'Some text before\n{"key": "value"}'
        result = self.llm_filter._extract_json_from_content(content)
        assert result == '{"key": "value"}'

    def test_extract_json_with_extra_content_both_sides(self):
        """Test extracting JSON with extra content before and after."""
        content = 'Text before\n{"key": "value"}\nText after'
        result = self.llm_filter._extract_json_from_content(content)
        assert result == '{"key": "value"}'

    def test_extract_nested_json(self):
        """Test extracting nested JSON objects."""
        content = """Some text
{
    "outer": {
        "inner": "value"
    },
    "array": [1, 2, 3]
}
More text"""
        result = self.llm_filter._extract_json_from_content(content)
        expected = """{
    "outer": {
        "inner": "value"
    },
    "array": [1, 2, 3]
}"""
        assert result == expected

    def test_extract_json_with_strings_containing_braces(self):
        """Test extracting JSON with strings that contain braces."""
        content = """Text before
{
    "message": "This string contains { and } braces",
    "code": "function() { return {}; }"
}
Text after"""
        result = self.llm_filter._extract_json_from_content(content)
        expected = """{
    "message": "This string contains { and } braces",
    "code": "function() { return {}; }"
}"""
        assert result == expected

    def test_extract_json_multiple_objects_takes_first(self):
        """Test that when multiple JSON objects exist, it takes the first complete one."""
        content = '{"first": "object"} {"second": "object"}'
        result = self.llm_filter._extract_json_from_content(content)
        assert result == '{"first": "object"}'

    def test_extract_json_no_json_found(self):
        """Test error when no JSON is found."""
        content = "No JSON here at all"
        with pytest.raises(ValueError, match="No JSON object found"):
            self.llm_filter._extract_json_from_content(content)

    def test_extract_json_unmatched_braces(self):
        """Test error when braces are unmatched."""
        content = '{"incomplete": "json"'
        with pytest.raises(ValueError, match="Unmatched braces"):
            self.llm_filter._extract_json_from_content(content)

    def test_extract_json_empty_content(self):
        """Test error when content is empty."""
        content = ""
        with pytest.raises(ValueError, match="No JSON object found"):
            self.llm_filter._extract_json_from_content(content)

    def test_extract_json_only_braces(self):
        """Test error when only braces exist."""
        content = "{}"
        result = self.llm_filter._extract_json_from_content(content)
        assert result == "{}"

    def test_extract_original_error_case(self):
        """Test the exact case from the user's error."""
        content = """{
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

        result = self.llm_filter._extract_json_from_content(content)
        expected = """{
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
  }"""
        assert result == expected
