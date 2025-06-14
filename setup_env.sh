#!/bin/bash

# Setup script for the feed aggregator project
echo "Setting up virtual environment and dependencies..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install project in development mode
echo "Installing project in development mode..."
pip install -e .

echo ""
echo "Setup complete!"
echo ""
echo "To use the feed aggregator:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the example in demo mode: python scripts/example_fetch.py"
echo "3. Or set environment variables for real Feedly API access:"
echo "   export FEEDLY_TOKEN='your_feedly_token'"
echo "   export FEEDLY_USER='your_feedly_user_id'"
echo "   python scripts/example_fetch.py"
echo ""
echo "To run tests: python -m pytest tests/test_fetcher.py -v"
