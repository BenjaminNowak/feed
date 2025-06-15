import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

import ollama
import yaml
from openai import OpenAI

from feed_aggregator.config.category_config import CategoryConfig

logger = logging.getLogger(__name__)


class LLMFilter:
    """Uses LLM to analyze and filter feed items."""

    REQUIRED_FIELDS = ["relevance_score", "summary", "key_topics"]
    PROVIDERS = Literal["openai", "ollama"]

    def __init__(
        self,
        provider: PROVIDERS = "openai",
        config_path: Optional[str] = None,
        category: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize LLM filter.

        Args:
            provider: LLM provider to use ('openai' or 'ollama')
            config_path: Path to prompts config file (overrides category)
            category: Category key to load prompts for (e.g., 'Tech', 'ML')
            api_key: Optional API key for OpenAI
        """
        self.provider = provider
        self.category = category
        self.config_path = config_path
        self.config = self._load_config(config_path, category)

        if provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable not set and no API key provided"
                )
            self.client = OpenAI(api_key=self.api_key)
        else:
            # Ollama runs locally, no auth needed
            self.client = None

    def _load_config(
        self, config_path: Optional[str] = None, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load prompts from config file or category-specific config.

        Args:
            config_path: Direct path to config file (takes precedence)
            category: Category key to load prompts for

        Returns:
            Configuration dictionary
        """
        # If config_path is provided, use it directly (backward compatibility)
        if config_path:
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    if not config or "llm_filter" not in config:
                        raise ValueError(
                            "Invalid config format: missing llm_filter section"
                        )
                    return config["llm_filter"]
            except (OSError, yaml.YAMLError, ValueError) as e:
                error_msg = f"Error loading config: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e

        # If category is provided, use CategoryConfig to get the prompts file
        if category:
            try:
                category_config = CategoryConfig()
                prompts_path = category_config.get_prompts_path(category)

                with open(prompts_path, "r") as f:
                    config = yaml.safe_load(f)
                    if not config or "llm_filter" not in config:
                        raise ValueError(
                            f"Invalid config format in {prompts_path}: missing llm_filter section"
                        )
                    return config["llm_filter"]
            except (OSError, yaml.YAMLError, ValueError) as e:
                error_msg = f"Error loading category config for '{category}': {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e

        # Fallback: try to load default prompts.yml (for backward compatibility)
        default_config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "prompts.yml",
        )

        try:
            with open(default_config_path, "r") as f:
                config = yaml.safe_load(f)
                if not config or "llm_filter" not in config:
                    raise ValueError(
                        "Invalid config format: missing llm_filter section"
                    )
                return config["llm_filter"]
        except (OSError, yaml.YAMLError, ValueError) as e:
            error_msg = (
                f"Error loading config: {str(e)}. "
                "Please provide either a config_path or category parameter, "
                "or ensure config/prompts.yml exists."
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def analyze_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single feed item.

        Args:
            item: Feed item to analyze

        Returns:
            Analysis results including relevance score, summary, and topics

        Raises:
            ValueError: If API response is invalid
            Exception: If API call fails
        """
        try:
            # Format prompts
            system_prompt = self.config["system_prompt"]
            user_prompt = self.config["user_prompt"].format(
                title=item["title"],
                content=item["content"],
            )

            if self.provider == "openai":
                return self._analyze_with_openai(system_prompt, user_prompt)
            else:
                return self._analyze_with_ollama(system_prompt, user_prompt)

        except Exception as e:
            logger.error(f"Error analyzing item {item.get('_id')}: {str(e)}")
            raise

    def _analyze_with_openai(
        self, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        """Call OpenAI API for analysis."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.config["openai"]["model"],
            messages=messages,
            temperature=self.config["openai"]["temperature"],
            response_format=self.config["openai"]["response_format"],
        )

        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid response format: {str(e)}") from e

        # Add metadata about the analysis
        metadata = {
            "prompt_version": self.config.get("version", "1.0"),
            "system_prompt": system_prompt,
            "user_prompt_template": self.config["user_prompt"],
            "model": self.config["openai"]["model"],
            "temperature": self.config["openai"]["temperature"],
            "timestamp": str(response.created),
            "provider": "openai",
            "category": self.category,
            "config_path": self.config_path,
        }
        result["_analysis_metadata"] = metadata

        self._validate_result(result)
        return result

    def _analyze_with_ollama(
        self, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        """Call Ollama API for analysis."""
        prompt = (
            f"{system_prompt}\n\n"
            "You must respond with a valid JSON object.\n\n"
            f"{user_prompt}"
        )

        try:
            response = ollama.chat(
                model=self.config["ollama"]["model"],
                messages=[
                    {"role": "system", "content": "You are a JSON-only responder"},
                    {"role": "user", "content": prompt},
                ],
                options={
                    "temperature": self.config["ollama"]["temperature"],
                    "format": self.config["ollama"]["format"],
                },
            )

            logger.info(f"Raw Ollama response: {response}")

            # Get response content from message
            if hasattr(response, "message"):
                content = response.message.content
            elif isinstance(response, dict) and "message" in response:
                content = response["message"]["content"]
            else:
                raise ValueError(f"No content found in Ollama response: {response}")

            # Clean the content - remove any markdown code block markers and thinking process
            content = content.strip()

            # Remove any markdown markers first
            content = content.replace("```json", "").replace("```", "").strip()

            # Try to extract valid JSON using a more robust approach
            extracted_json = self._extract_json_from_content(content)

            try:
                result = json.loads(extracted_json)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in response: {str(e)}\nContent: {extracted_json}"
                ) from e

            # Add metadata about the analysis
            metadata = {
                "prompt_version": self.config.get("version", "1.0"),
                "system_prompt": system_prompt,
                "user_prompt_template": self.config["user_prompt"],
                "model": self.config["ollama"]["model"],
                "temperature": self.config["ollama"]["temperature"],
                "timestamp": str(
                    response.created_at if hasattr(response, "created_at") else "N/A"
                ),
                "provider": "ollama",
                "category": self.category,
                "config_path": self.config_path,
            }
            result["_analysis_metadata"] = metadata

            self._validate_result(result)
            return result

        except Exception as e:
            error_msg = f"Ollama API error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _extract_json_from_content(self, content: str) -> str:
        """Extract valid JSON from content that may have extra text.

        This method uses a more robust approach to find and extract JSON
        by counting braces to find the complete JSON object.

        Args:
            content: Raw content that may contain JSON with extra text

        Returns:
            Extracted JSON string

        Raises:
            ValueError: If no valid JSON object is found
        """
        content = content.strip()

        # Find the first opening brace
        json_start = content.find("{")
        if json_start == -1:
            raise ValueError("No JSON object found in content")

        # Count braces to find the matching closing brace
        brace_count = 0
        json_end = json_start

        for i in range(json_start, len(content)):
            char = content[i]
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break

        if brace_count != 0:
            raise ValueError("Unmatched braces in JSON content")

        extracted = content[json_start:json_end]

        # Validate that we extracted something that looks like JSON
        if not extracted.strip():
            raise ValueError("Empty JSON content extracted")

        return extracted

    def _validate_result(self, result: Dict[str, Any]) -> None:
        """Validate LLM response has required fields."""
        for field in self.REQUIRED_FIELDS:
            if field not in result:
                raise ValueError(f"Missing required field in response: {field}")

    def batch_analyze(
        self, items: List[Dict[str, Any]], batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """Analyze multiple feed items.

        Args:
            items: List of feed items to analyze
            batch_size: Number of items to process in parallel (not implemented yet)

        Returns:
            List of analysis results
        """
        results = []
        for item in items:
            try:
                result = self.analyze_item(item)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch analysis: {str(e)}")
                # Continue processing remaining items
                continue

        return results
