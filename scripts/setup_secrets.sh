#!/bin/bash
set -e

# Configuration
SECRETS_DIR="docker/secrets"
ENV_FILE=".env"
ENV_EXAMPLE="docker/.env.example"

# Create secrets directory
mkdir -p "$SECRETS_DIR"

# Function to safely write secrets
write_secret() {
    local secret_name=$1
    local prompt_text=$2
    local secret_file="$SECRETS_DIR/${secret_name}.txt"
    
    echo -n "$prompt_text: "
    read -s secret_value
    echo
    
    # Validate non-empty input
    if [ -z "$secret_value" ]; then
        echo "Error: Secret value cannot be empty"
        return 1
    fi
    
    echo "$secret_value" > "$secret_file"
    chmod 600 "$secret_file"
    echo "Created secret: $secret_name"
}

# Function to create .env file
create_env_file() {
    if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        echo "Created .env file from template"
    else
        echo ".env file already exists"
    fi
}

# Function to validate directory structure
validate_structure() {
    local required_dirs=("docker" "config" "output")
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "Creating directory: $dir"
            mkdir -p "$dir"
        fi
    done
}

# Main execution
echo "Setting up Intelligence Feed System..."
echo "======================================"

# Validate directory structure
validate_structure

# Create .env file
create_env_file

# Collect secrets
echo "Setting up secrets in $SECRETS_DIR"
echo "--------------------------------"

# MongoDB secrets
write_secret "mongo_username" "Enter MongoDB username"
write_secret "mongo_password" "Enter MongoDB password"

# API secrets
write_secret "feedly_token" "Enter Feedly API token"
write_secret "openai_api_key" "Enter OpenAI API key"
write_secret "github_token" "Enter GitHub token"

# Set restrictive permissions on secrets directory
chmod 700 "$SECRETS_DIR"

echo
echo "Setup completed successfully!"
echo "----------------------------"
echo "Secrets directory: $SECRETS_DIR"
echo "Environment file: $ENV_FILE"
echo
echo "Next steps:"
echo "1. Review and customize $ENV_FILE"
echo "2. Run 'docker-compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d' for development"
echo "   or"
echo "   Run 'docker-compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d' for production"
