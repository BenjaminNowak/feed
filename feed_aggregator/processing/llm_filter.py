import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

import ollama
import yaml
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMFilter:
    """Uses LLM to analyze and filter feed items."""

    REQUIRED_FIELDS = ["relevance_score", "summary", "key_topics"]
    PROVIDERS = Literal["openai", "ollama"]

    def __init__(
        self,
        provider: PROVIDERS = "openai",
        config_path: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize LLM filter.

        Args:
            provider: LLM provider to use ('openai' or 'ollama')
            config_path: Path to prompts config file
            api_key: Optional API key for OpenAI
        """
        self.provider = provider
        self.config = self._load_config(config_path)

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

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load prompts from config file."""
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "prompts.yml",
            )

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

            # Clean the content - remove any markdown code block markers
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in response: {str(e)}\nContent: {content}"
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
            }
            result["_analysis_metadata"] = metadata

            self._validate_result(result)
            return result

        except Exception as e:
            error_msg = f"Ollama API error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

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
