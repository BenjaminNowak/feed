import os

from feedly.api_client.session import FeedlySession


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

        # Handle different stream ID patterns
        if (
            "category/global.all" in stream_id
            or stream_id == "user/-/category/global.all"
        ):
            try:
                items = self._get_category_stream(count)
                return {"id": stream_id, "items": items}
            except Exception as err:
                # If API call fails, raise the exception
                msg = f"Feedly API call failed: {err}"
                raise RuntimeError(msg) from err
        else:
            # For other stream IDs, try to parse and use the API
            # This is a simplified implementation
            msg = f"Stream ID {stream_id} not yet supported with official client"
            raise NotImplementedError(msg)

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
