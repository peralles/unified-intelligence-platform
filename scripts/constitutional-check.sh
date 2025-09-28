#!/bin/bash

# Constitutional Compliance Check Script
# Validates adherence to the Five Constitutional Principles

set -e

echo "🏛️ Unified Data Intelligence Platform - Constitutional Compliance Check"
echo "================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        ((FAILED++))
    fi
}

check_warning() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    ((WARNINGS++))
}

echo ""
echo "Principle I: Strict Data Governance"
echo "-----------------------------------"

# Check for canonical schema
if [ -f "event-ingestion-api/deployment/schema/radar-signal-schema.json" ]; then
    check_result 0 "Canonical RadarSignal schema exists"
else
    check_result 1 "Canonical RadarSignal schema missing"
fi

# Check for schema validation in services
if grep -r "gojsonschema" event-ingestion-api/ > /dev/null 2>&1; then
    check_result 0 "Schema validation library found"
else
    check_result 1 "Schema validation not implemented"
fi

echo ""
echo "Principle II: Scalable, Real-Time Architecture"
echo "---------------------------------------------"

# Check for serverless configuration
if [ -f "event-ingestion-api/deployment/function.yaml" ] || grep -r "gcloud functions" event-ingestion-api/ > /dev/null 2>&1; then
    check_result 0 "Serverless deployment configuration found"
else
    check_result 1 "Serverless deployment configuration missing"
fi

# Check for event-driven messaging
if grep -r "pubsub\|pub/sub" event-ingestion-api/ > /dev/null 2>&1; then
    check_result 0 "Event-driven messaging (Pub/Sub) configured"
else
    check_result 1 "Event-driven messaging not found"
fi

echo ""
echo "Principle III: High Observability"
echo "--------------------------------"

# Check for structured logging
if grep -r "json\|structured" event-ingestion-api/ > /dev/null 2>&1; then
    check_result 0 "Structured logging implementation found"
else
    check_result 1 "Structured logging not implemented"
fi

# Check for tracing setup
if grep -r "trace\|opentelemetry" event-ingestion-api/ > /dev/null 2>&1; then
    check_result 0 "Tracing implementation found"
else
    check_warning "Distributed tracing not yet implemented (acceptable for Phase 1)"
fi

echo ""
echo "Principle IV: Modular and Reusable Design"  
echo "----------------------------------------"

# Check for service contracts
if find . -name "*.yaml" -o -name "*.yml" | grep -E "(openapi|swagger)" > /dev/null 2>&1; then
    check_result 0 "API contracts (OpenAPI) found"
else
    check_warning "API contracts not yet documented (should be added)"
fi

# Check for modular structure
if [ -d "event-ingestion-api/src/services" ] && [ -d "event-ingestion-api/src/handlers" ]; then
    check_result 0 "Modular service architecture found"
else
    check_result 1 "Modular architecture not properly structured"
fi

echo ""
echo "Principle V: Phased Evolution"
echo "----------------------------"

# Check for feature flag support
if grep -r "feature.*flag\|flag.*feature" . > /dev/null 2>&1; then
    check_result 0 "Feature flag support found"
else
    check_warning "Feature flags not yet implemented (recommended for Phase 2+)"
fi

# Check for version management  
if [ -f "go.mod" ] || [ -f "package.json" ]; then
    check_result 0 "Dependency version management found"
else
    check_result 1 "Package management not configured"
fi

echo ""
echo "Development Standards Compliance"
echo "==============================="

# Check for tests
if find . -name "*_test.go" -o -name "*.test.js" -o -name "*test*.py" | head -1 > /dev/null 2>&1; then
    check_result 0 "Test files found"
else
    check_result 1 "No test files found - violates TDD requirement"
fi

# Check for documentation
if [ -f "README.md" ] && [ -f "CONSTITUTION.md" ]; then
    check_result 0 "Core documentation exists"
else
    check_result 1 "Missing required documentation"
fi

# Check for Infrastructure as Code
if find . -name "*.tf" -o -name "terraform*" > /dev/null 2>&1; then
    check_result 0 "Infrastructure as Code (Terraform) found"
else
    check_warning "Infrastructure as Code not yet implemented"
fi

echo ""
echo "================================================================="
echo "Constitutional Compliance Summary"
echo "================================================================="
echo -e "✅ ${GREEN}Passed${NC}: $PASSED"
echo -e "❌ ${RED}Failed${NC}: $FAILED"  
echo -e "⚠️  ${YELLOW}Warnings${NC}: $WARNINGS"

if [ $FAILED -eq 0 ]; then
    echo -e "\n🎉 ${GREEN}Constitutional compliance achieved!${NC}"
    echo "The platform adheres to the foundational principles."
    exit 0
else
    echo -e "\n🚨 ${RED}Constitutional violations detected!${NC}"
    echo "Please address the failed checks before proceeding."
    exit 1
fi