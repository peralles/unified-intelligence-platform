#!/bin/bash

# Schema Validation Script for RadarSignal Events
# Validates JSON event files against the canonical schema

set -e

SCHEMA_FILE="deployment/schema/radar-signal-schema.json"
EXAMPLES_DIR="examples/events"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 RadarSignal Event Schema Validation${NC}"
echo "======================================="

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}❌ Schema file not found: $SCHEMA_FILE${NC}"
    exit 1
fi

echo -e "📋 Using schema: ${BLUE}$SCHEMA_FILE${NC}"
echo ""

# Function to validate a single JSON file
validate_file() {
    local file="$1"
    local filename=$(basename "$file")
    
    echo -n "Validating $filename... "
    
    # Check if file exists and is readable
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ File not found${NC}"
        return 1
    fi
    
    # Validate JSON syntax first
    if ! jq empty "$file" >/dev/null 2>&1; then
        echo -e "${RED}❌ Invalid JSON syntax${NC}"
        return 1
    fi
    
    # Use Python to validate against JSON schema (since we don't have Go validation tool yet)
    python3 -c "
import json
import sys
from jsonschema import validate, ValidationError

try:
    with open('$SCHEMA_FILE', 'r') as schema_file:
        schema = json.load(schema_file)
    
    with open('$file', 'r') as event_file:
        event = json.load(event_file)
    
    validate(instance=event, schema=schema)
    print('✅ Valid')
    sys.exit(0)
    
except ValidationError as e:
    print(f'❌ Schema violation: {e.message}')
    sys.exit(1)
    
except FileNotFoundError as e:
    print(f'❌ File error: {e}')
    sys.exit(1)
    
except json.JSONDecodeError as e:
    print(f'❌ JSON error: {e}')
    sys.exit(1)
    
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
" 2>/dev/null
    
    return $?
}

# Install jsonschema if not available
if ! python3 -c "import jsonschema" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Installing jsonschema Python library...${NC}"
    pip3 install jsonschema >/dev/null 2>&1 || {
        echo -e "${RED}❌ Failed to install jsonschema. Please install manually: pip3 install jsonschema${NC}"
        exit 1
    }
fi

# Validate specific file if provided as argument
if [ $# -gt 0 ]; then
    echo "Validating specified file(s):"
    echo ""
    
    for file in "$@"; do
        validate_file "$file"
    done
    
    exit 0
fi

# Validate all example files
if [ -d "$EXAMPLES_DIR" ]; then
    echo "Validating all example events:"
    echo ""
    
    VALID_COUNT=0
    INVALID_COUNT=0
    
    for file in "$EXAMPLES_DIR"/*.json; do
        if [ -f "$file" ]; then
            if validate_file "$file"; then
                ((VALID_COUNT++))
            else
                ((INVALID_COUNT++))
            fi
        fi
    done
    
    echo ""
    echo "================================="
    echo -e "${GREEN}✅ Valid events: $VALID_COUNT${NC}"
    echo -e "${RED}❌ Invalid events: $INVALID_COUNT${NC}"
    
    if [ $INVALID_COUNT -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}💡 Note: Some invalid examples are intentional for testing validation logic${NC}"
    fi
    
else
    echo -e "${YELLOW}⚠️  Examples directory not found: $EXAMPLES_DIR${NC}"
fi

echo ""
echo -e "${BLUE}💡 Usage Examples:${NC}"
echo "  ./scripts/validate-schema.sh                           # Validate all examples"
echo "  ./scripts/validate-schema.sh path/to/event.json        # Validate specific file"
echo "  cat event.json | jq . && ./scripts/validate-schema.sh event.json  # Check syntax then validate"