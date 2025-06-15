"""Module for fetching content from URLs."""
import logging
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class URLFetcher:
    """Fetches and extracts content from URLs."""

    def __init__(self, timeout: int = 10):
        """Initialize URL fetcher.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        # Set a reasonable user agent
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; FeedAggregator/1.0; +http://example.com)"
            }
        )

    def fetch_url_content(self, url: str) -> Optional[Dict]:
        """Fetch content from a URL.

        Args:
            url: URL to fetch content from

        Returns:
            Dictionary containing extracted content or None if failed
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style"]):
                element.decompose()

            # Extract main content
            content = {
                "title": self._extract_title(soup),
                "description": self._extract_description(soup),
                "main_content": self._extract_main_content(soup),
                "raw_text": soup.get_text(strip=True),
            }

            return content

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch URL {url}: {str(e)}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content", "")

        # Fallback to regular title
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.text.strip()

        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract description from HTML."""
        # Try meta description first
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc:
            return meta_desc.get("content", "")

        # Try og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc.get("content", "")

        return ""

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML.

        Uses a simple heuristic to find the main content area:
        - Looks for common content container elements
        - Falls back to largest text block if no container found
        """
        # Common content container IDs/classes
        content_selectors = [
            "article",
            '[role="main"]',
            "#main-content",
            "#content",
            ".post-content",
            ".entry-content",
            ".article-content",
        ]

        # Try each selector
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                return content.get_text(strip=True)

        # Fallback: find largest text block
        paragraphs = soup.find_all("p")
        if paragraphs:
            largest = max(paragraphs, key=lambda p: len(p.get_text()))
            return largest.get_text(strip=True)

        return ""

    def close(self):
        """Close the requests session."""
        self.session.close()
