# Architecture Overview

This project aggregates news from multiple sources and produces curated RSS feeds. A Feedly client ingests content while a language model reduces it based on prompts stored in `prompts.yml`. The resulting summaries are written to XML files (starting with `feed.xml`).

```
+------------+      +--------------+      +---------------+
| News Feeds | -->  | Feed Fetcher | -->  | LLM Summarizer |
+------------+      +--------------+      +---------------+
                                    \--> feeds/*.xml
```

Code lives in `feed_aggregator/` with unit tests under `tests/`. Use `python -m unittest` to run tests. A sample script demonstrating Feedly access is in `scripts/example_fetch.py`.
