# syntax=docker/dockerfile:1

# Base stage for shared configurations
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY feed_aggregator/ feed_aggregator/
COPY config/ config/
COPY scripts/ scripts/

# Development stage
FROM base as development
ENV PYTHONUNBUFFERED=1
ENV DEBUG=1

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    black \
    flake8 \
    mypy

# Keep container running for development
CMD ["tail", "-f", "/dev/null"]

# Production stage
FROM base as production
ENV PYTHONUNBUFFERED=1
ENV DEBUG=0

# Create non-root user
RUN useradd -m -r feeduser && \
    chown -R feeduser:feeduser /app

# Switch to non-root user
USER feeduser

# Function to read secrets from files
COPY --chown=feeduser:feeduser <<EOF /app/feed_aggregator/read_secrets.py
import os

def read_secret(secret_file):
    if os.path.exists(secret_file):
        with open(secret_file, 'r') as f:
            return f.read().strip()
    return None

# Read secrets from files
MONGODB_USERNAME = read_secret('/run/secrets/mongo_username')
MONGODB_PASSWORD = read_secret('/run/secrets/mongo_password')
FEEDLY_TOKEN = read_secret('/run/secrets/feedly_token')
OPENAI_API_KEY = read_secret('/run/secrets/openai_api_key')
GITHUB_TOKEN = read_secret('/run/secrets/github_token')

# Set environment variables
if MONGODB_USERNAME:
    os.environ['MONGODB_USERNAME'] = MONGODB_USERNAME
if MONGODB_PASSWORD:
    os.environ['MONGODB_PASSWORD'] = MONGODB_PASSWORD
if FEEDLY_TOKEN:
    os.environ['FEEDLY_TOKEN'] = FEEDLY_TOKEN
if OPENAI_API_KEY:
    os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY
if GITHUB_TOKEN:
    os.environ['GITHUB_TOKEN'] = GITHUB_TOKEN
EOF

# Main application script
COPY --chown=feeduser:feeduser <<EOF /app/feed_aggregator/main.py
import os
import time
import logging
from feed_aggregator.read_secrets import *
from feed_aggregator.fetcher import FeedlyFetcher

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Feed Processor")
    
    # Initialize fetcher
    fetcher = FeedlyFetcher(
        token=os.getenv('FEEDLY_TOKEN'),
        user_id=os.getenv('FEEDLY_USER')
    )
    
    # Main processing loop
    while True:
        try:
            logger.info("Processing feeds...")
            # TODO: Implement main processing logic
            
            # Sleep until next processing interval
            interval = int(os.getenv('PROCESSING_INTERVAL', 1800))
            logger.info(f"Sleeping for {interval} seconds")
            time.sleep(interval)
            
        except Exception as e:
            logger.error(f"Error in processing loop: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main()
EOF

# Run the application
CMD ["python", "-m", "feed_aggregator.main"]
