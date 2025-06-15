# Article Reconciliation Feature

## Overview

The reconciliation feature allows you to check for processed articles from the last day that may have been missed in the XML feed and add them back. This is useful for ensuring that all high-quality articles that were processed are properly included in the feed.

## Usage

```bash
python scripts/process_categories_runner.py --reconcile
```

## How It Works

1. **Date Range Calculation**: The feature looks for articles processed in the last 24 hours ending at the current time when the command is run.

2. **Article Query**: It queries MongoDB for articles that:
   - Have `processing_status` set to "processed"
   - Have an LLM relevance score >= the configured quality threshold (default 0.6)
   - Were published or crawled within the last day

3. **XML Comparison**: It parses the existing `feed.xml` file and extracts all article GUIDs to create a set of already-published articles.

4. **Missing Article Detection**: It compares the processed articles against the XML feed to find articles that are missing.

5. **Reconciliation**: For any missing articles:
   - Marks them as ready for publishing by clearing the `published_to_feed` flag
   - Updates the XML feed using the existing `update_feed` functionality
   - Commits and pushes the changes to the repository

## Error Handling

- If no processed articles are found from yesterday, the process exits gracefully
- If the XML file doesn't exist or can't be parsed, it treats all processed articles as missing
- MongoDB connection errors are handled and reported
- The process ensures the MongoDB connection is properly closed

## Command Line Validation

The `--reconcile` option cannot be combined with other options:
- `--reconcile` with category names will result in an error
- `--reconcile` with `--all` will result in an error
- `--reconcile` with `--list` will result in an error

## Example Output

```
============================================================
RECONCILING PROCESSED ARTICLES AGAINST XML FEED
============================================================
Looking for articles processed between:
  Start: 2025-06-14 00:08:25 UTC
  End: 2025-06-15 00:08:25 UTC
Found 17 high-quality processed articles from yesterday
Found 20 articles already in XML feed
Found 0 processed articles missing from XML feed

Sample of processed articles checked:
  ✓ Rocky and Alma Linux Still Going Strong. RHEL Adds... (Score: 0.85)
  ✓ New nanoparticle-based genetic delivery system tar... (Score: 0.85)
  ✓ PersonaLens: A Benchmark for Personalization... (Score: 0.9)
All processed articles are already in the XML feed. No reconciliation needed.
```

When articles need reconciliation:
```
============================================================
RECONCILING PROCESSED ARTICLES AGAINST XML FEED
============================================================
Looking for articles processed between:
  Start: 2025-06-14 00:08:25 UTC
  End: 2025-06-15 00:08:25 UTC
Found 5 high-quality processed articles from yesterday
Found 2 articles already in XML feed
Found 3 processed articles missing from XML feed
  Missing: Example Article Title 1... (ID: abc123...)
  Missing: Example Article Title 2... (ID: def456...)
  Missing: Example Article Title 3... (ID: ghi789...)

Sample of processed articles checked:
  ✓ Already Published Article... (Score: 0.85)
  ✗ Missing Article 1... (Score: 0.8)
  ✗ Missing Article 2... (Score: 0.9)
Marked 3 articles as ready for publishing
Updating XML feed with missing articles...
Committing and pushing changes...

============================================================
RECONCILIATION COMPLETED SUCCESSFULLY
============================================================
Articles reconciled: 3
Feed updated and pushed to repository
```

## Use Cases

- **Daily Maintenance**: Run as part of a daily cron job to ensure no articles are missed
- **Error Recovery**: Use after system issues to recover any articles that may have been processed but not published
- **Quality Assurance**: Verify that the feed contains all expected high-quality articles

## Technical Details

- Uses the same quality threshold as configured in the global configuration
- Leverages the existing `update_feed.py` and git commit/push functionality
- Maintains consistency with the existing article processing pipeline
- Includes comprehensive test coverage for all scenarios
