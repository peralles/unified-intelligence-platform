# Radar Signals Event Ingestion API - Testing Guide

> **Comprehensive testing strategy and examples for the event ingestion API specification**

## 🧪 Testing Philosophy

Following the constitutional principle of **High Observability** and **Strict Data Governance**, our testing strategy ensures:

- **Schema Compliance**: 100% validation coverage for canonical RadarSignal format
- **Contract Adherence**: API behavior matches OpenAPI specification exactly  
- **Performance Standards**: Meet sub-100ms latency and 1000+ events/second throughput
- **Reliability Targets**: 99.9% availability with graceful error handling
- **Observability**: Comprehensive logging and tracing validation

## 🎯 Test Categories

### 1. Schema Validation Tests

**Purpose**: Validate canonical RadarSignal schema enforcement

#### Valid Event Tests
```bash
# Test valid events
./scripts/validate-schema.sh examples/events/user-signup-completed.json
./scripts/validate-schema.sh examples/events/payment-transaction-failed.json
./scripts/validate-schema.sh examples/events/inventory-item-updated.json
```

**Expected**: All return `✅ Valid`

#### Invalid Event Tests
```bash  
# Test intentionally invalid events
./scripts/validate-schema.sh examples/events/invalid-missing-fields.json
./scripts/validate-schema.sh examples/events/invalid-malformed-data.json
```

**Expected**: Both return schema violation errors with specific field details

#### Edge Case Tests

**Missing Required Fields**:
```json
{
  "eventId": "123e4567-e89b-42d3-a456-426614174000",
  "eventTimestamp": "2025-09-28T14:30:00.000Z"
  // Missing: eventSource, eventType, eventVersion, payload
}
```

**Invalid Data Types**:
```json
{
  "eventId": 12345,  // Should be string UUID
  "eventTimestamp": "not-a-timestamp",
  "eventSource": "",  // Empty string not allowed
  "eventType": "invalid-format-no-dots",
  "eventVersion": "not.semantic.version.format", 
  "payload": "should-be-object-not-string"
}
```

**Boundary Value Tests**:
```json
{
  "eventId": "123e4567-e89b-42d3-a456-426614174000",
  "eventTimestamp": "2025-09-28T14:30:00.000Z",
  "eventSource": "a".repeat(101),  // Exceeds maxLength: 100
  "eventType": "valid.event.type",
  "eventVersion": "1.0.0",
  "payload": {} // Empty object (invalid - minProperties: 1)
}
```

### 2. API Contract Tests

**Purpose**: Validate OpenAPI specification compliance

#### POST /events - Success Cases

**Test**: Valid event submission
```bash
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d @examples/events/user-signup-completed.json
```

**Expected Response**: `202 Accepted`
```json
{
  "status": "accepted",
  "eventId": "123e4567-e89b-42d3-a456-426614174000", 
  "traceId": "trace_abc123def456",
  "timestamp": "2025-09-28T14:30:00.123Z"
}
```

#### POST /events - Error Cases

**Test**: Schema validation failure
```bash
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d @examples/events/invalid-missing-fields.json
```

**Expected Response**: `400 Bad Request`
```json
{
  "error": "VALIDATION_FAILED",
  "message": "Event validation failed against canonical schema",
  "details": [
    {
      "field": "eventType", 
      "message": "Required field 'eventType' is missing"
    }
  ],
  "traceId": "trace_def456ghi789",
  "timestamp": "2025-09-28T14:30:00.123Z"
}
```

**Test**: Oversized payload
```bash
# Generate payload > 1MB
dd if=/dev/zero bs=1048577 count=1 | base64 > large-payload.json
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d @large-payload.json
```

**Expected Response**: `413 Payload Too Large`

#### GET /healthz Tests

**Test**: Healthy service
```bash
curl -X GET https://api-url/healthz
```

**Expected Response**: `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2025-09-28T14:30:00.123Z",
  "version": "1.0.0",
  "dependencies": {
    "pubsub": "healthy",
    "schema_registry": "healthy"
  },
  "metrics": {
    "uptime_seconds": 86400,
    "requests_per_second": 150.5,
    "average_latency_ms": 45.2,
    "error_rate_percent": 0.1
  }
}
```

### 3. Integration Tests

**Purpose**: End-to-end workflow validation with real Pub/Sub

#### Event Flow Test
```bash
# 1. Submit valid event
EVENT_ID=$(uuidgen)
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d '{
    "eventId": "'$EVENT_ID'",
    "eventTimestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'",
    "eventSource": "test-client",
    "eventType": "test.integration.submitted",
    "eventVersion": "1.0.0", 
    "payload": {"testId": "integration-001"}
  }'

# 2. Verify event appears in Pub/Sub topic
# (Implementation-specific verification)
```

#### Dependency Failure Test
```bash
# Simulate Pub/Sub unavailability
# (Implementation-specific - e.g., network policy, service shutdown)

# Submit event during outage
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d @examples/events/user-signup-completed.json
```

**Expected**: `503 Service Unavailable` with retry-after headers

### 4. Performance Tests

**Purpose**: Validate latency and throughput targets

#### Latency Test
```bash
# Single request latency measurement
for i in {1..100}; do
  time curl -X POST https://api-url/events \
    -H "Content-Type: application/json" \
    -d @examples/events/user-signup-completed.json
done | grep real | awk '{print $2}' | sort -n
```

**Target**: 95th percentile < 100ms

#### Throughput Test
```bash
# Concurrent request load testing
hey -n 10000 -c 50 -m POST \
  -H "Content-Type: application/json" \
  -d @examples/events/user-signup-completed.json \
  https://api-url/events
```

**Target**: >1000 requests/second sustained

#### Scaling Test
```bash
# Gradual load increase to test auto-scaling
for concurrent in 1 5 10 25 50 100; do
  echo "Testing with $concurrent concurrent requests..."
  hey -n 1000 -c $concurrent -m POST \
    -H "Content-Type: application/json" \
    -d @examples/events/user-signup-completed.json \
    https://api-url/events
  sleep 30  # Allow scaling
done
```

### 5. Observability Tests

**Purpose**: Validate logging, tracing, and monitoring

#### Trace ID Propagation Test
```bash
# Submit event with custom trace header (if supported)
TRACE_ID="trace_test_$(date +%s)"
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -H "X-Trace-ID: $TRACE_ID" \
  -d @examples/events/user-signup-completed.json

# Verify trace ID appears in:
# 1. Response body
# 2. Access logs 
# 3. Application logs
# 4. Pub/Sub message attributes
```

#### Error Logging Test
```bash
# Generate validation error
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d @examples/events/invalid-missing-fields.json

# Verify structured error logging:
# 1. Error type and details logged
# 2. Request metadata captured
# 3. No sensitive data in logs
# 4. Trace ID correlation available
```

### 6. Security Tests

**Purpose**: Validate input sanitization and security controls

#### Input Validation Tests
```bash
# Test various malicious payloads
curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d '{"eventId": "<script>alert(1)</script>"}' # XSS attempt

curl -X POST https://api-url/events \
  -H "Content-Type: application/json" \
  -d '{"eventId": "'; DROP TABLE events; --"}' # SQL injection attempt
```

**Expected**: All return `400 Bad Request` with validation errors

#### Rate Limiting Test
```bash
# Exceed rate limits
for i in {1..1000}; do
  curl -X POST https://api-url/events \
    -H "Content-Type: application/json" \
    -d @examples/events/user-signup-completed.json &
done
wait
```

**Expected**: Eventually return `429 Too Many Requests` with appropriate headers

## 🚀 Automated Test Execution

### Test Suite Runner
```bash
#!/bin/bash
# Run complete test suite

echo "🧪 Running Radar Signals API Test Suite"
echo "======================================"

# 1. Schema validation tests
echo "1️⃣ Schema Validation Tests..."
./scripts/validate-schema.sh

# 2. API contract tests (when API is implemented)  
echo "2️⃣ API Contract Tests..."
# ./scripts/contract-tests.sh

# 3. Integration tests (when infrastructure is ready)
echo "3️⃣ Integration Tests..."  
# ./scripts/integration-tests.sh

# 4. Performance tests
echo "4️⃣ Performance Tests..."
# ./scripts/performance-tests.sh

echo "✅ Test suite complete!"
```

### Continuous Integration
```yaml
# .github/workflows/test.yml
name: API Tests
on: [push, pull_request]

jobs:
  schema-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: pip install jsonschema
      - name: Validate schemas
        run: ./event-ingestion-api/scripts/validate-schema.sh

  contract-tests:
    runs-on: ubuntu-latest
    needs: schema-validation
    steps:
      - uses: actions/checkout@v4
      - name: Run contract tests
        run: # Implementation-specific commands
        
  constitutional-compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check constitutional compliance
        run: ./scripts/constitutional-check.sh
```

## ✅ Test Acceptance Criteria

### Schema Validation
- [ ] All valid example events pass validation
- [ ] All invalid example events fail with specific error messages
- [ ] Schema enforces all required fields
- [ ] Schema validates data types and formats correctly
- [ ] Schema prevents additional properties

### API Contract  
- [ ] Valid events return `202 Accepted` with proper response format
- [ ] Invalid events return `400 Bad Request` with detailed errors
- [ ] Health endpoint returns proper status and metrics
- [ ] Error responses include trace IDs for correlation
- [ ] HTTP status codes match OpenAPI specification

### Performance
- [ ] 95th percentile latency < 100ms
- [ ] Sustained throughput > 1000 events/second
- [ ] Auto-scaling from zero to peak load
- [ ] Graceful degradation under extreme load

### Observability
- [ ] Structured JSON logging implemented
- [ ] Trace IDs propagated through request lifecycle
- [ ] Error details logged without sensitive data
- [ ] Metrics available for monitoring dashboards

### Security  
- [ ] Input validation prevents malicious payloads
- [ ] Rate limiting protects against abuse
- [ ] Error messages don't expose sensitive information
- [ ] Request size limits prevent resource exhaustion

---

**Testing Status**: ✅ **Schema Validation Ready** | 🔄 **Contract Tests Pending Implementation**

*This testing guide ensures the Radar Signals Event Ingestion API meets all constitutional requirements and specification standards before deployment.*