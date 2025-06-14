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

# Load environment variables from Docker secrets if they exist
echo "Checking for Docker secrets..."
if [ -d "docker/secrets" ]; then
    echo "Loading environment variables from Docker secrets..."
    
    if [ -f "docker/secrets/mongo_username.txt" ]; then
        export MONGODB_USERNAME=$(cat docker/secrets/mongo_username.txt)
        echo "✓ MONGODB_USERNAME loaded from secrets"
    fi
    
    if [ -f "docker/secrets/mongo_password.txt" ]; then
        export MONGODB_PASSWORD=$(cat docker/secrets/mongo_password.txt)
        echo "✓ MONGODB_PASSWORD loaded from secrets"
    fi
    
    if [ -f "docker/secrets/feedly_token.txt" ]; then
        export FEEDLY_TOKEN=$(cat docker/secrets/feedly_token.txt)
        echo "✓ FEEDLY_TOKEN loaded from secrets"
    fi
    
    if [ -f "docker/secrets/openai_api_key.txt" ]; then
        export OPENAI_API_KEY=$(cat docker/secrets/openai_api_key.txt)
        echo "✓ OPENAI_API_KEY loaded from secrets"
    fi
    
    if [ -f "docker/secrets/github_token.txt" ]; then
        export GITHUB_TOKEN=$(cat docker/secrets/github_token.txt)
        echo "✓ GITHUB_TOKEN loaded from secrets"
    fi
    
    echo ""
    echo "Environment variables loaded from Docker secrets."
    echo "You can now run scripts without manually setting environment variables."
else
    echo "No Docker secrets directory found. You'll need to set environment variables manually."
fi

echo ""
echo "Setup complete!"
echo ""
echo "To use the feed aggregator:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the example in demo mode: python scripts/example_fetch.py"
echo "3. Or set environment variables for real API access:"
echo "   export FEEDLY_TOKEN='your_feedly_token'"
echo "   export FEEDLY_USER='your_feedly_user_id'"
echo "   export MONGODB_USERNAME='your_mongodb_username'"
echo "   export MONGODB_PASSWORD='your_mongodb_password'"
echo "   export OPENAI_API_KEY='your_openai_api_key'"
echo "   python scripts/example_fetch.py"
echo ""
echo "For Docker deployment, see docker/.env.example for configuration"
echo "and use Docker secrets for production credentials."
echo ""
echo "To run tests: python -m pytest tests/ -v"
