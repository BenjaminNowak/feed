import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DataNormalizer:
    """Normalizes data from various sources into a standard format."""

    SUPPORTED_SOURCES = ["feedly", "rss", "test"]
    REQUIRED_FIELDS = ["id", "title"]

    def normalize(self, item: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Normalize an item from a specific source into standard format.

        Args:
            item: Raw item from source
            source: Source identifier (feedly, rss, etc.)

        Returns:
            Normalized item matching MongoDB schema

        Raises:
            ValueError: If source is invalid or required fields are missing
        """
        # Validate source
        if source not in self.SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported source: {source}")

        # Validate required fields
        for field in self.REQUIRED_FIELDS:
            if field not in item and (source != "rss" or field != "id"):
                raise ValueError(f"Missing required field: {field}")

        # Create base normalized item
        normalized = {
            "source": source,
            "source_id": self._get_source_id(item, source),
            "title": item["title"],
            "content": self._get_content(item, source),
            "url": self._get_url(item, source),
            "author": self._get_author(item),
            "published_date": self._get_published_date(item, source),
            "ingested_date": datetime.now(timezone.utc),
            "tags": self._get_tags(item, source),
            "metadata": self._get_metadata(item, source),
            "processing_status": "pending",
        }

        # Generate unique ID
        normalized["_id"] = self._generate_id(normalized)

        return normalized

    def _get_source_id(self, item: Dict[str, Any], source: str) -> str:
        """Get source-specific ID."""
        if source == "rss":
            return item.get("guid", item.get("link", ""))
        return item["id"]

    def _get_content(self, item: Dict[str, Any], source: str) -> str:
        """Extract content from item."""
        if source == "feedly":
            content = item.get("content", {}).get("content")
            if not content:
                content = item.get("summary", {}).get("content", "")
            return content
        elif source == "rss":
            return item.get("description", "")
        return item.get("content", "")

    def _get_url(self, item: Dict[str, Any], source: str) -> Optional[str]:
        """Get item URL."""
        if source == "feedly":
            alternates = item.get("alternate", [])
            if alternates and "href" in alternates[0]:
                return alternates[0]["href"]
        elif source == "rss":
            return item.get("link")
        return None

    def _get_author(self, item: Dict[str, Any]) -> Optional[str]:
        """Get item author."""
        return item.get("author")

    def _get_published_date(
        self, item: Dict[str, Any], source: str
    ) -> Optional[datetime]:
        """Convert published date to UTC datetime."""
        if source == "feedly":
            # Feedly uses milliseconds since epoch
            if "published" in item:
                return datetime.fromtimestamp(item["published"] / 1000, tz=timezone.utc)
        elif source == "rss":
            # RSS uses RFC 2822 format
            if "pubDate" in item:
                try:
                    return datetime.strptime(
                        item["pubDate"], "%a, %d %b %Y %H:%M:%S %Z"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        return datetime.now(timezone.utc)

    def _get_tags(self, item: Dict[str, Any], source: str) -> List[str]:
        """Get item tags."""
        if source == "feedly":
            return item.get("keywords", [])
        elif source == "rss":
            categories = item.get("category", [])
            if isinstance(categories, str):
                return [categories]
            return categories
        return []

    def _get_metadata(self, item: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Get source-specific metadata."""
        metadata = {}
        if source == "feedly":
            origin = item.get("origin", {})
            if "title" in origin:
                metadata["source_feed"] = origin["title"]
        return metadata

    def _generate_id(self, item: Dict[str, Any]) -> str:
        """Generate unique ID based on item content."""
        # Create a string combining key fields
        unique_string = f"{item['source']}:{item['source_id']}:{item['title']}"

        # Generate SHA-256 hash
        return hashlib.sha256(unique_string.encode("utf-8")).hexdigest()
