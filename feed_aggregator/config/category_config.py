"""Category configuration management."""

import os
from typing import Any, Dict, List, Optional

import yaml


class CategoryConfig:
    """Manages category configurations for feed processing."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize category configuration.

        Args:
            config_path: Path to categories.yml file
        """
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "categories.yml",
            )

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load categories configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
                if not config or "categories" not in config:
                    raise ValueError(
                        "Invalid config format: missing categories section"
                    )
                return config
        except (OSError, yaml.YAMLError, ValueError) as e:
            raise ValueError(f"Error loading category config: {str(e)}") from e

    def get_category_config(self, category_key: str) -> Dict[str, Any]:
        """Get configuration for a specific category.

        Args:
            category_key: Category key (e.g., 'ML', 'Tech')

        Returns:
            Category configuration dictionary

        Raises:
            ValueError: If category not found
        """
        if category_key not in self.config["categories"]:
            available = list(self.config["categories"].keys())
            raise ValueError(
                f"Category '{category_key}' not found. Available: {available}"
            )

        return self.config["categories"][category_key]

    def get_all_categories(self) -> List[str]:
        """Get list of all available category keys."""
        return list(self.config["categories"].keys())

    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration settings."""
        return self.config.get("global", {})

    def get_prompts_path(self, category_key: str) -> str:
        """Get the prompts file path for a category.

        Args:
            category_key: Category key

        Returns:
            Full path to the category's prompts file
        """
        category_config = self.get_category_config(category_key)
        prompts_file = category_config["prompts_file"]

        return os.path.join(os.path.dirname(self.config_path), "prompts", prompts_file)

    def get_quality_threshold(self, category_key: str) -> float:
        """Get quality threshold for a category.

        Args:
            category_key: Category key

        Returns:
            Quality threshold (0.0-1.0)
        """
        category_config = self.get_category_config(category_key)
        return category_config.get("quality_threshold", 0.6)

    def get_high_quality_target(self, category_key: str) -> int:
        """Get high quality article target for a category.

        Args:
            category_key: Category key

        Returns:
            Number of high quality articles needed before updating feed
        """
        category_config = self.get_category_config(category_key)
        return category_config.get("high_quality_target", 10)

    def get_feedly_category(self, category_key: str) -> str:
        """Get the Feedly category name for a category.

        Args:
            category_key: Category key

        Returns:
            Feedly category name
        """
        category_config = self.get_category_config(category_key)
        return category_config["feedly_category"]

    def get_output_feed(self, category_key: str) -> str:
        """Get the output feed filename for a category.

        Args:
            category_key: Category key

        Returns:
            Output feed filename
        """
        category_config = self.get_category_config(category_key)
        return category_config.get("output_feed", "feed.xml")
