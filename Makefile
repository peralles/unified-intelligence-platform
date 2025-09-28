# Unified Data Intelligence Platform Makefile
# Provides common tasks aligned with Constitutional Principles

.PHONY: help constitutional-check setup-dev lint test build deploy clean

# Default target
help: ## Show this help message
	@echo "🏛️ Unified Data Intelligence Platform"
	@echo "===================================="
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

constitutional-check: ## 🏛️ Check compliance with Constitutional Principles
	@echo "Running Constitutional Compliance Check..."
	@./scripts/constitutional-check.sh

setup-dev: ## 🛠️ Set up development environment
	@echo "Setting up development environment..."
	@echo "- Checking constitutional compliance..."
	@./scripts/constitutional-check.sh || echo "⚠️  Some constitutional violations found - proceed with caution"
	@echo "- Installing pre-commit hooks..."
	@[ -f .git/hooks/pre-commit ] || cp scripts/constitutional-check.sh .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Development environment setup complete"

lint: ## 🔍 Run linting across all services
	@echo "Running platform-wide linting..."
	@if [ -d "event-ingestion-api" ]; then \
		echo "Linting Event Ingestion API..."; \
		cd event-ingestion-api && go fmt ./... && go vet ./...; \
	fi

test: ## 🧪 Run tests across all services with coverage
	@echo "Running platform-wide tests..."
	@if [ -d "event-ingestion-api" ]; then \
		echo "Testing Event Ingestion API..."; \
		cd event-ingestion-api && go test -v -coverage ./...; \
	fi

build: ## 🏗️ Build all services
	@echo "Building all platform services..."
	@if [ -d "event-ingestion-api" ]; then \
		echo "Building Event Ingestion API..."; \
		cd event-ingestion-api && go build -o bin/event-ingestion-api ./src; \
	fi

deploy: constitutional-check ## 🚀 Deploy services (requires constitutional compliance)
	@echo "Deploying platform services..."
	@echo "✅ Constitutional compliance verified"
	@if [ -d "event-ingestion-api" ]; then \
		echo "Deploying Event Ingestion API..."; \
		cd event-ingestion-api && gcloud functions deploy radar-signals-ingestion --gen2 --runtime=go121 --source=. --entry-point=IngestEvent --trigger=http; \
	fi

clean: ## 🧹 Clean build artifacts and temporary files
	@echo "Cleaning build artifacts..."
	@find . -name "bin" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.log" -type f -delete 2>/dev/null || true
	@find . -name ".DS_Store" -type f -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Constitutional enforcement targets
.PHONY: enforce-governance enforce-architecture enforce-observability enforce-modularity enforce-evolution

enforce-governance: ## 🔒 Validate data governance compliance
	@echo "Enforcing Constitutional Principle I: Strict Data Governance"
	@./scripts/constitutional-check.sh | grep -A 10 "Principle I"

enforce-architecture: ## ⚡ Validate scalable architecture compliance  
	@echo "Enforcing Constitutional Principle II: Scalable, Real-Time Architecture"
	@./scripts/constitutional-check.sh | grep -A 10 "Principle II"

enforce-observability: ## 👀 Validate observability compliance
	@echo "Enforcing Constitutional Principle III: High Observability" 
	@./scripts/constitutional-check.sh | grep -A 10 "Principle III"

enforce-modularity: ## 🔧 Validate modular design compliance
	@echo "Enforcing Constitutional Principle IV: Modular and Reusable Design"
	@./scripts/constitutional-check.sh | grep -A 10 "Principle IV"

enforce-evolution: ## 🚀 Validate phased evolution compliance
	@echo "Enforcing Constitutional Principle V: Phased Evolution"
	@./scripts/constitutional-check.sh | grep -A 10 "Principle V"