# Radar Signals Event Ingestion API - Development Guidelines

Auto-generated from implementation plan. Last updated: September 28, 2025

## Active Technologies

- **Runtime**: Python 3.11 (Google Cloud Functions 2nd generation)
- **Schema Validation**: jsonschema v4.19.1+ with pre-compiled validators
- **Cloud Services**: google-cloud-pubsub v2.18.4+, functions-framework v3.4.0+
- **Data Models**: pydantic v2.4.2+ for request/response validation
- **Testing**: pytest v7.4.2+, pytest-asyncio, pytest-mock for comprehensive testing
- **Platform**: Google Cloud Platform - serverless architecture
- **Message Bus**: Google Pub/Sub for asynchronous event publishing
- **Deployment**: Cloud Functions with Terraform (Infrastructure as Code)

## Project Structure

```
event-ingestion-api/
├── src/
│   ├── main.py                    # Cloud Function entry point
│   ├── models/
│   │   ├── __init__.py
│   │   ├── radar_signal.py        # Pydantic models for request/response
│   │   └── errors.py              # Custom exception classes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── validator.py           # JSON schema validation service
│   │   ├── publisher.py           # Pub/Sub publishing service
│   │   └── health.py              # Health check service
│   └── utils/
│       ├── __init__.py
│       ├── logging.py             # Structured logging utilities
│       └── config.py              # Environment configuration
├── tests/
│   ├── unit/
│   │   ├── test_validator.py      # Schema validation unit tests
│   │   ├── test_publisher.py      # Pub/Sub publishing unit tests
│   │   └── test_health.py         # Health check unit tests
│   ├── integration/
│   │   ├── test_function_flow.py  # End-to-end function tests
│   │   └── test_pubsub_integration.py # Real Pub/Sub integration tests
│   └── contract/
│       ├── test_events_api.py     # API contract tests (POST /)
│       └── test_health_api.py     # Health endpoint contract tests
├── deployment/
│   ├── schema/
│   │   └── radar-signal-schema.json  # Canonical event schema
│   ├── terraform/
│   │   ├── main.tf                # GCP infrastructure
│   │   ├── cloud-function.tf      # Function deployment
│   │   ├── pubsub.tf              # Pub/Sub topic creation
│   │   └── variables.tf           # Configuration variables
│   └── cloudbuild.yaml           # CI/CD pipeline configuration
├── requirements.txt               # Python dependencies
├── main.py                       # Cloud Function entry point (symlink to src/main.py)
└── .env.example                  # Environment variables template
```

## Commands

### Development

```bash
# Initialize Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Run local development server
functions-framework --target=main --debug --port=8080

# Test endpoint locally
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d @examples/events/user-signup-completed.json

# Health check
curl http://localhost:8080/healthz
```

### Testing & Validation

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/ -v                    # Unit tests
pytest tests/contract/ -v                # Contract tests  
pytest tests/integration/ -v             # Integration tests

# Run with coverage
pytest --cov=src --cov-report=html

# Validate JSON schema
python -m src.services.validator examples/events/user-signup-completed.json

# Validate against canonical schema
./scripts/validate-schema.sh
```

### Cloud Functions Deployment

```bash
# Deploy function
gcloud functions deploy radar-signals-ingestion \
  --gen2 \
  --runtime=python311 \
  --source=. \
  --entry-point=main \
  --trigger=http \
  --memory=512MB \
  --timeout=60s \
  --max-instances=100 \
  --set-env-vars="PUBSUB_TOPIC=radar-signals-topic,PROJECT_ID=$(gcloud config get-value project)"

# Deploy with Terraform
cd deployment/terraform
terraform init
terraform plan
terraform apply

# Test deployed function
curl -X POST https://us-central1-PROJECT_ID.cloudfunctions.net/radar-signals-ingestion \
  -H "Content-Type: application/json" \
  -d @examples/events/user-signup-completed.json
```

### Infrastructure Management

```bash
# Create Pub/Sub resources
gcloud pubsub topics create radar-signals-topic
gcloud pubsub subscriptions create radar-signals-test-sub --topic=radar-signals-topic

# Monitor function logs
gcloud functions logs read radar-signals-ingestion --limit=50

# Monitor Pub/Sub messages
gcloud pubsub subscriptions pull radar-signals-test-sub --limit=10
```

## Code Style

### Python Best Practices

- Follow PEP 8 style guidelines with Black formatting
- Use type hints for all function signatures and class attributes
- Implement error handling with custom exception classes
- Use Pydantic for data validation and serialization
- Structure logs as JSON for Cloud Operations integration
- Handle async operations properly for Pub/Sub publishing

### Naming Conventions

```python
# Classes: PascalCase
class RadarSignalEvent:
class ValidationService:

# Functions: snake_case
def validate_event() -> ValidationResult:
def publish_to_pubsub() -> str:

# Constants: UPPER_CASE
MAX_PAYLOAD_SIZE = 1048576
DEFAULT_TIMEOUT = 60

# Variables: snake_case
event_data = request.get_json()
trace_id = generate_trace_id()
```

### Error Handling Pattern

```python
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class ErrorType(Enum):
    VALIDATION_FAILED = ("VALIDATION_FAILED", 400, False)
    PAYLOAD_TOO_LARGE = ("PAYLOAD_TOO_LARGE", 413, False)
    RATE_LIMITED = ("RATE_LIMITED", 429, True)
    SERVICE_UNAVAILABLE = ("SERVICE_UNAVAILABLE", 503, True)
    INTERNAL_ERROR = ("INTERNAL_ERROR", 500, True)

class APIError(Exception):
    def __init__(self, error_type: ErrorType, message: str, details: Optional[List] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or []
        super().__init__(message)
    
    @property
    def status_code(self) -> int:
        return self.error_type.value[1]
    
    @property
    def retryable(self) -> bool:
        return self.error_type.value[2]

# Usage in main function
def main(request):
    try:
        # Process request
        return success_response
    except APIError as e:
        return error_response(e)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return internal_error_response()
```

### Performance Optimization Patterns

```python
from functools import lru_cache
import jsonschema
import json

# Pre-compile JSON schema validator (cached globally)
@lru_cache(maxsize=1)
def get_compiled_validator():
    with open('deployment/schema/radar-signal-schema.json') as f:
        schema = json.load(f)
    return jsonschema.Draft202012Validator(schema)

# Async Pub/Sub publishing
from google.cloud import pubsub_v1
from concurrent.futures import ThreadPoolExecutor

class OptimizedPublisher:
    def __init__(self, project_id: str, topic_name: str):
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_name)
    
    async def publish_event(self, event_data: dict, trace_id: str) -> str:
        message_data = json.dumps(event_data).encode('utf-8')
        future = self.publisher.publish(
            self.topic_path, 
            message_data,
            trace_id=trace_id
        )
        return future.result(timeout=30)
```

### Structured Logging Pattern

```python
import logging
import json
from datetime import datetime
from typing import Any, Dict

class StructuredLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log(self, level: str, message: str, trace_id: str = None, **kwargs):
        log_entry = {
            "severity": level.upper(),
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace": f"projects/PROJECT_ID/traces/{trace_id}" if trace_id else None,
            **kwargs
        }
        self.logger.info(json.dumps(log_entry))

# Usage
logger = StructuredLogger()
logger.log("INFO", "Event validated successfully", 
           trace_id="abc123", event_id="123e4567-e89b-42d3-a456-426614174000")
```

### Testing Patterns

```python
import pytest
from unittest.mock import Mock, patch
from src.services.validator import ValidationService
from src.models.radar_signal import RadarSignalEvent

class TestValidationService:
    @pytest.fixture
    def validator(self):
        return ValidationService()
    
    @pytest.fixture
    def valid_event_data(self):
        return {
            "event_id": "123e4567-e89b-42d3-a456-426614174000",
            "event_timestamp": "2025-09-28T14:30:00.000Z",
            "event_source": "test-service",
            "event_type": "test.validation.success",
            "event_version": "1.0.0",
            "payload": {"test": "data"}
        }
    
    def test_valid_event_passes_validation(self, validator, valid_event_data):
        # Test successful validation
        result = validator.validate_event(valid_event_data)
        assert isinstance(result, RadarSignalEvent)
        assert result.event_id == "123e4567-e89b-42d3-a456-426614174000"
    
    @pytest.mark.parametrize("missing_field", [
        "event_id", "event_timestamp", "event_source", "event_type", "event_version", "payload"
    ])
    def test_missing_required_field_fails(self, validator, valid_event_data, missing_field):
        # Test validation failures
        del valid_event_data[missing_field]
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_event(valid_event_data)
        assert missing_field in str(exc_info.value)

# Contract testing
@pytest.mark.contract
def test_post_events_endpoint_contract(client):
    response = client.post('/', json=valid_event_data)
    assert response.status_code == 202
    assert "event_id" in response.json
    assert "trace_id" in response.json
```

## Recent Changes

1. **Implementation Planning (2025-09-28)**: Created comprehensive Python-based serverless implementation plan
   - Finalized Python 3.11 + Cloud Functions 2nd Gen architecture
   - Selected optimized technology stack (jsonschema, pydantic, google-cloud-pubsub)
   - Defined performance targets: <100ms latency, >1000 events/second throughput
   - Created detailed data models with Pydantic validation
   - Generated OpenAPI contract specification for implementation validation
   - Established comprehensive testing strategy with quickstart validation scenarios

<!-- MANUAL ADDITIONS START -->
<!-- Add any manual development guidelines, team conventions, or project-specific notes here -->
<!-- MANUAL ADDITIONS END -->
