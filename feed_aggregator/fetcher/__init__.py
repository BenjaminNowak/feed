"""Feed fetcher package."""
import os

from feedly.api_client.session import FeedlySession

from feed_aggregator.fetcher.url_fetcher import URLFetcher


class FeedlyFetcher:
    """Wrapper around feedly/python-api-client's FeedlySession."""

    def __init__(
        self,
        token: str | None = None,
        user_id: str | None = None,
        demo_mode: bool = False,
    ):
        self.token = token or os.environ.get("FEEDLY_TOKEN")
        self.user_id = user_id or os.environ.get("FEEDLY_USER")
        self.demo_mode = demo_mode

        if not self.demo_mode and not self.token:
            raise ValueError(
                "FEEDLY_TOKEN environment variable not set (or use demo_mode=True)"
            )

        if not self.demo_mode:
            self.session = FeedlySession(auth=self.token, user_id=self.user_id)
        else:
            self.session = None

    def _get_category_stream(self, count: int) -> list:
        """Get stream contents from the first available category."""
        print("Fetching stream from Feedly API...")
        available_categories = list(
            self.session.user.user_categories.name2stream.keys()
        )
        if not available_categories:
            raise ValueError("No categories found in Feedly account")

        print(f"Available categories: {available_categories}")
        category = self.session.user.user_categories.get(available_categories[0])
        stream = category.stream_contents()
        print(f"Stream object created: {type(stream)}")

        return self._process_stream_entries(stream, count)

    def _process_stream_entries(self, stream, count: int) -> list:
        """Process stream entries and return items."""
        items = []
        entries_processed = 0
        max_entries_to_check = 100  # Prevent infinite loops

        for entry in stream:
            entries_processed += 1
            print(
                f"Processing entry {entries_processed}: "
                f"{type(entry)} - {entry is not None}"
            )

            if entries_processed > max_entries_to_check:
                print("Reached maximum entries to check (100), stopping")
                break

            if len(items) >= count:
                print(f"Got {count} items, stopping")
                break

            if entry is None:
                print("Skipping None entry")
                continue

            items.extend(self._process_single_entry(entry))

        print(
            f"Finished processing. Got {len(items)} items "
            f"from {entries_processed} entries"
        )
        return items

    def _process_single_entry(self, entry) -> list:
        """Process a single entry and return as list."""
        if hasattr(entry, "json"):
            print("Entry has json attribute, adding to items")
            return [entry.json]
        if isinstance(entry, dict):
            print("Entry is dict, adding to items")
            return [entry]
        print(f"Skipping entry of type {type(entry)}")
        return []

    def get_stream_contents(self, stream_id: str, count: int = 10) -> dict:
        """Return contents for a given stream id."""
        if self.demo_mode:
            return self._get_demo_data(stream_id, count)

        try:
            # Extract category name from stream ID
            if "category/" in stream_id:
                category_name = stream_id.split("category/", 1)[1].strip()
                print(f"Looking for category: {category_name}")

                # For global.all, use first available category
                if category_name == "global.all":
                    items = self._get_category_stream(count)
                    return {"id": stream_id, "items": items}

                # Get the specific category
                category = self.session.user.user_categories.get(category_name)
                if not category:
                    raise ValueError(f"Category not found: {category_name}")

                # Get stream contents
                stream = category.stream_contents()
                items = self._process_stream_entries(stream, count)
                return {"id": stream_id, "items": items}
            else:
                # For non-category streams, use default behavior
                items = self._get_category_stream(count)
                return {"id": stream_id, "items": items}

        except Exception as err:
            # If API call fails, raise the exception
            msg = f"Feedly API call failed: {err}"
            raise RuntimeError(msg) from err

    def _find_entry_in_stream(self, stream, entry_id: str) -> dict | None:
        """Search for an entry in a stream by its ID.

        Args:
            stream: The stream to search in
            entry_id: The entry ID to look for

        Returns:
            dict | None: The entry data if found, None otherwise
        """
        for entry in stream:
            if not entry:
                continue

            entry_data = entry.json if hasattr(entry, "json") else entry
            if isinstance(entry_data, dict) and entry_data.get("id") == entry_id:
                return entry_data
        return None

    def get_entry_by_url(self, entry_url: str) -> dict:
        """Fetch a single entry by its Feedly URL or entry ID.

        Args:
            entry_url: Either a full Feedly URL (https://feedly.com/i/entry/<entry_id>)
                      or just the entry ID

        Returns:
            dict: The entry data

        Raises:
            ValueError: If URL format is invalid or entry not found
            RuntimeError: If the API call fails
        """
        if self.demo_mode:
            return self._get_demo_data("demo_stream", 1)["items"][0]

        # Extract entry ID from URL or use directly if it's just an ID
        if entry_url.startswith("https://feedly.com/i/entry/"):
            entry_id = entry_url.split("/entry/", 1)[1]
        else:
            entry_id = entry_url

        try:
            # Get available categories
            categories = list(self.session.user.user_categories.name2stream.keys())
            if not categories:
                raise ValueError("No categories found in Feedly account")

            # Search each category's stream for the entry
            for category_name in categories:
                category = self.session.user.user_categories.get(category_name)
                stream = category.stream_contents()

                entry_data = self._find_entry_in_stream(stream, entry_id)
                if entry_data:
                    return entry_data

            raise ValueError(f"Entry not found: {entry_id}")

        except Exception as err:
            msg = f"Failed to fetch entry {entry_id}: {err}"
            raise RuntimeError(msg) from err

    def _get_demo_data(self, stream_id: str, count: int) -> dict:
        """Return sample data for demo purposes."""
        sample_items = [
            {
                "id": "demo_item_1",
                "title": (
                    "AlphaEvolve: A Gemini-Powered Coding Agent "
                    "for Designing Advanced Algorithms"
                ),
                "summary": {
                    "content": (
                        "DeepMind introduces AlphaEvolve, a revolutionary AI system "
                        "that combines the power of Gemini with evolutionary algorithms "
                        "to automatically design and optimize complex algorithms."
                    )
                },
                "author": "DeepMind Team",
                "published": 1733097600000,
                "origin": {
                    "streamId": "feed/https://deepmind.google/rss.xml",
                    "title": "DeepMind Blog",
                    "htmlUrl": "https://deepmind.google/discover/blog/",
                },
                "alternate": [
                    {
                        "href": (
                            "https://deepmind.google/discover/blog/"
                            "alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/"
                        ),
                        "type": "text/html",
                    }
                ],
            },
            {
                "id": "demo_item_2",
                "title": "Sample Feed Item 2",
                "summary": {
                    "content": (
                        "This is a second sample feed item for demonstration purposes."
                    )
                },
                "author": "Demo Author",
                "published": 1733011200000,
                "origin": {
                    "streamId": stream_id,
                    "title": "Demo Feed",
                    "htmlUrl": "https://example.com",
                },
                "alternate": [
                    {"href": "https://example.com/article2", "type": "text/html"}
                ],
            },
        ]

        # Return only the requested count
        return {"id": stream_id, "items": sample_items[:count]}


__all__ = ["FeedlyFetcher", "URLFetcher"]
