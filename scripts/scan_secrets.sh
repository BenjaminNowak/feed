#!/bin/bash
set -e

# Custom patterns to detect potential secrets
# Add more patterns as needed
PATTERNS=(
    # API Keys and Tokens
    '[a-zA-Z0-9_-]{32,}'  # Generic API key pattern
    'sk-[a-zA-Z0-9]{32,}' # OpenAI API key pattern
    'ghp_[a-zA-Z0-9]{36}' # GitHub personal access token
    'xox[baprs]-([0-9a-zA-Z]{10,48})' # Slack token
    
    # Database connection strings
    'mongodb(\+srv)?://[^"'\'']*'
    'postgres://[^"'\'']*'
    'mysql://[^"'\'']*'
    
    # AWS
    'AKIA[0-9A-Z]{16}'  # AWS Access Key ID
    '[0-9a-zA-Z/+]{40}'  # AWS Secret Access Key
    
    # Private keys and certificates
    '-----BEGIN.*PRIVATE.*KEY-----'
    '-----BEGIN.*CERTIFICATE-----'
    
    # Environment variables that might contain secrets
    '(API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|CREDENTIALS)(["\s]*=[\s"]*|[:]\s*)[^\s"]{8,}'
    
    # Database user creation patterns (MongoDB, SQL, etc.)
    'pwd.*:.*"[^"]{6,}"'  # pwd: "password" patterns
    'password.*:.*"[^"]{6,}"'  # password: "password" patterns
    'user.*:.*"[a-zA-Z0-9_-]{3,}"'  # user: "username" patterns
    'createUser.*pwd.*:.*"[^"]{6,}"'  # MongoDB createUser with hardcoded pwd
    
    # Hardcoded credentials in various formats
    '"[a-zA-Z0-9_-]{3,}".*:.*"[^"]{8,}"'  # "user": "password" patterns
    '(username|userid|user_id).*=.*"[a-zA-Z0-9_-]{3,}"'  # username="value"
    '(password|passwd|pwd).*=.*"[^"]{6,}"'  # password="value"
    
    # Specific patterns for common hardcoded values
    '"[a-zA-Z0-9_-]{3,}".*:.*"[^"]*[><!@#$%^&*()_+{}|:<>?~`\[\]\\;,./-][^"]*"'  # Passwords with special chars
)

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load ignore patterns from .secretsignore
load_ignore_patterns() {
    IGNORE_PATTERNS=()
    if [ -f ".secretsignore" ]; then
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip empty lines and comments
            if [ -z "$line" ] || [[ "$line" =~ ^[[:space:]]*# ]]; then
                continue
            fi
            # Extract pattern (everything before #)
            pattern=$(echo "$line" | sed 's/[[:space:]]*#.*$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            if [ ! -z "$pattern" ]; then
                IGNORE_PATTERNS+=("$pattern")
            fi
        done < ".secretsignore"
    fi
}

# Check if a line should be ignored
should_ignore() {
    local line="$1"
    for pattern in "${IGNORE_PATTERNS[@]}"; do
        if echo "$line" | grep -q -E "$pattern"; then
            return 0
        fi
    done
    return 1
}

# Function to check a single file
check_file() {
    local file="$1"
    local found_secrets=0
    
    # Skip binary files
    if file "$file" | grep -q "binary"; then
        return 0
    fi
    
    # Skip files in certain directories
    if echo "$file" | grep -q "^docker/secrets/\|^venv/\|^\.git/"; then
        return 0
    fi
    
    echo "Checking $file..."
    
    for pattern in "${PATTERNS[@]}"; do
        # Search for pattern in file
        matches=$(grep -Ein -e "$pattern" "$file" 2>/dev/null || true)
        if [ ! -z "$matches" ]; then
            while IFS= read -r match_line; do
                if [ ! -z "$match_line" ]; then
                    # Extract just the content part after line number
                    line_content=$(echo "$match_line" | sed 's/^[0-9]*://')
                    # Check if line should be ignored
                    if ! should_ignore "$line_content"; then
                        if [ "$found_secrets" -eq 0 ]; then
                            echo -e "${RED}WARNING: Potential secret found in $file${NC}"
                        fi
                        echo -e "${YELLOW}Found potential secret in line:${NC}"
                        echo "$match_line"
                        echo -e "${YELLOW}(Matched pattern: $pattern)${NC}"
                        echo
                        found_secrets=1
                    fi
                fi
            done <<< "$matches"
        fi
    done
    
    return $found_secrets
}

# Main execution
echo "Running custom secret scanner..."
echo "==============================="

# Load ignore patterns
load_ignore_patterns
if [ ${#IGNORE_PATTERNS[@]} -gt 0 ]; then
    echo "Loaded ${#IGNORE_PATTERNS[@]} ignore patterns from .secretsignore"
fi

# Get staged files if running as pre-commit hook
if [ -z "$1" ]; then
    FILES=$(git diff --cached --name-only)
else
    FILES="$@"
fi

# Exit code
EXIT_CODE=0

# Check each file
for file in $FILES; do
    if [ -f "$file" ]; then
        check_file "$file" || EXIT_CODE=1
    fi
done

if [ $EXIT_CODE -eq 0 ]; then
    echo "No secrets detected."
else
    echo -e "${RED}WARNING: Potential secrets were found!${NC}"
    echo "Please review the findings and ensure no sensitive data is being committed."
    echo "If these are false positives, consider:"
    echo "1. Using environment variables"
    echo "2. Storing secrets in docker/secrets/"
    echo "3. Using docker secrets management"
fi

exit $EXIT_CODE
