import os
from feed_aggregator.fetcher import FeedlyFetcher
import json


def main():
    # Use FEEDLY_STREAM_ID environment variable or a default
    stream_id = os.environ.get("FEEDLY_STREAM_ID", "user/-/category/global.all")
    fetcher = FeedlyFetcher()
    data = fetcher.get_stream_contents(stream_id, count=1)
    print(json.dumps(data, indent=2)[:200])


if __name__ == "__main__":
    main()
