# Quickstart Guide: Radar Signals Event Ingestion API

**Implementation Target**: Python Cloud Function on Google Cloud Platform  
**Validation Strategy**: Implementation against API contract specification  
**Date**: September 28, 2025

## 🎯 Purpose

This quickstart provides step-by-step validation scenarios to verify the implementation meets all specification requirements, constitutional principles, and performance targets. Execute these scenarios to ensure the API functions correctly before production deployment.

## 🚀 Prerequisites

### Development Environment
```bash
# Required tools
python --version  # Should be 3.11+
gcloud --version  # Google Cloud SDK
curl --version    # For API testing
jq --version      # For JSON processing

# Required GCP setup
gcloud auth login
gcloud config set project unified-intelligence-platform
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable logging.googleapis.com
```

### Local Development Setup
```bash
# Install Functions Framework for local testing
pip install functions-framework[signatures]

# Install required dependencies
pip install -r requirements.txt

# Start local development server
functions-framework --target=main --debug --port=8080
```

### GCP Infrastructure Setup
```bash
# Create Pub/Sub topic for event publishing
gcloud pubsub topics create radar-signals-topic

# Create subscription for testing (optional)
gcloud pubsub subscriptions create radar-signals-test-sub \
  --topic=radar-signals-topic

# Grant necessary permissions
gcloud projects add-iam-policy-binding unified-intelligence-platform \
  --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

## ✅ Validation Scenarios

### Scenario 1: Successful Event Ingestion

**Objective**: Verify complete happy path from HTTP request to Pub/Sub publish

**Test Steps**:

1. **Submit Valid Event**:
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -H "X-Trace-ID: test-trace-001" \
  -d '{
    "event_id": "123e4567-e89b-42d3-a456-426614174000",
    "event_timestamp": "2025-09-28T14:30:00.000Z",
    "event_source": "quickstart-test",
    "event_type": "test.validation.success",
    "event_version": "1.0.0",
    "payload": {
      "test_case": "successful_ingestion",
      "validation_run": 1
    }
  }'
```

2. **Verify Response**:
```bash
# Expected: HTTP 202 Accepted
{
  "status": "accepted",
  "event_id": "123e4567-e89b-42d3-a456-426614174000",
  "trace_id": "test-trace-001",
  "timestamp": "2025-09-28T14:30:00.123Z",
  "message_id": "1234567890123456"
}
```

3. **Verify Headers**:
```bash
# Check response includes required headers
curl -I -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '@examples/events/user-signup-completed.json'

# Expected headers:
# X-Trace-ID: <trace-identifier>
# X-Message-ID: <pubsub-message-id>
# Content-Type: application/json
```

4. **Verify Pub/Sub Message**:
```bash
# Pull message from test subscription
gcloud pubsub subscriptions pull radar-signals-test-sub \
  --limit=1 --format=json

# Verify message contains original event data unmodified
```

**Acceptance Criteria**:
- [ ] HTTP 202 response received
- [ ] Response contains all required fields (status, event_id, trace_id, timestamp)
- [ ] Response trace_id matches request trace_id
- [ ] Pub/Sub message published successfully
- [ ] Message payload exactly matches original event (no transformation)
- [ ] Response time <100ms (measure with `time curl ...`)

---

### Scenario 2: Schema Validation Rejection

**Objective**: Verify strict canonical schema enforcement with detailed error messages

**Test Steps**:

1. **Submit Event Missing Required Field**:
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "123e4567-e89b-42d3-a456-426614174000",
    "event_timestamp": "2025-09-28T14:30:00.000Z",
    "event_source": "quickstart-test",
    "event_version": "1.0.0",
    "payload": {
      "test_case": "missing_event_type"
    }
  }'
```

2. **Verify Error Response**:
```bash
# Expected: HTTP 400 Bad Request
{
  "error": "VALIDATION_FAILED",
  "message": "Event validation failed against canonical schema",
  "details": [
    {
      "field": "event_type",
      "message": "Required field 'event_type' is missing",
      "code": "MISSING_FIELD"
    }
  ],
  "trace_id": "<trace-identifier>",
  "timestamp": "2025-09-28T14:30:00.123Z",
  "retryable": false
}
```

3. **Submit Event with Invalid UUID**:
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "not-a-valid-uuid",
    "event_timestamp": "2025-09-28T14:30:00.000Z",
    "event_source": "quickstart-test",
    "event_type": "test.validation.invalid_uuid",
    "event_version": "1.0.0",
    "payload": {
      "test_case": "invalid_uuid_format"
    }
  }'
```

4. **Submit Event with Invalid Timestamp**:
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "123e4567-e89b-42d3-a456-426614174000",
    "event_timestamp": "invalid-timestamp-format",
    "event_source": "quickstart-test",
    "event_type": "test.validation.invalid_timestamp",
    "event_version": "1.0.0",
    "payload": {
      "test_case": "invalid_timestamp"
    }
  }'
```

**Acceptance Criteria**:
- [ ] All invalid events return HTTP 400 Bad Request
- [ ] Error responses include specific field-level validation details
- [ ] Error messages are human-readable and actionable
- [ ] `retryable` field correctly set to `false` for validation errors
- [ ] No events published to Pub/Sub for validation failures
- [ ] Error response includes trace_id for debugging

---

### Scenario 3: High-Volume Concurrent Processing

**Objective**: Verify performance under concurrent load meets throughput requirements

**Test Steps**:

1. **Generate Load Test Events**:
```bash
# Create 100 unique test events
for i in {1..100}; do
  cat > "test_event_${i}.json" << EOF
{
  "event_id": "$(uuidgen | tr '[:upper:]' '[:lower:]')",
  "event_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
  "event_source": "load-test-client",
  "event_type": "test.load.concurrent",
  "event_version": "1.0.0",
  "payload": {
    "test_case": "concurrent_load",
    "event_number": $i,
    "timestamp": "$(date -u +%s)"
  }
}
EOF
done
```

2. **Execute Concurrent Requests**:
```bash
# Submit 50 concurrent requests
for i in {1..50}; do
  curl -X POST http://localhost:8080/ \
    -H "Content-Type: application/json" \
    -d @test_event_${i}.json &
done
wait

# Measure response times
time_start=$(date +%s.%N)
for i in {51..100}; do
  curl -s -X POST http://localhost:8080/ \
    -H "Content-Type: application/json" \
    -d @test_event_${i}.json > /dev/null &
done
wait
time_end=$(date +%s.%N)
duration=$(echo "$time_end - $time_start" | bc)
throughput=$(echo "50 / $duration" | bc -l)
echo "Throughput: $throughput events/second"
```

3. **Verify All Events Processed**:
```bash
# Check Pub/Sub subscription for all messages
message_count=$(gcloud pubsub subscriptions pull radar-signals-test-sub \
  --limit=1000 --format="value(message.messageId)" | wc -l)
echo "Messages received: $message_count"
```

**Acceptance Criteria**:
- [ ] All concurrent requests return HTTP 202 (no failures)
- [ ] Throughput >50 events/second (target: >1000 for production)
- [ ] 95th percentile response time <100ms
- [ ] All events successfully published to Pub/Sub
- [ ] No request timeouts or connection errors
- [ ] Function memory usage stays within allocated limits

---

### Scenario 4: Health Check Validation

**Objective**: Verify health monitoring endpoint provides accurate status information

**Test Steps**:

1. **Check Healthy State**:
```bash
curl -X GET http://localhost:8080/healthz
```

2. **Verify Health Response**:
```bash
# Expected: HTTP 200 OK
{
  "status": "healthy",
  "timestamp": "2025-09-28T14:30:00.123Z",
  "version": "1.0.0",
  "dependencies": {
    "pubsub": {
      "status": "healthy",
      "response_time_ms": 12.5,
      "last_check": "2025-09-28T14:30:00.100Z"
    },
    "schema_registry": {
      "status": "healthy", 
      "response_time_ms": 1.2,
      "last_check": "2025-09-28T14:30:00.110Z"
    }
  },
  "metrics": {
    "uptime_seconds": 300,
    "requests_per_second": 0.0,
    "average_latency_ms": 0.0,
    "error_rate_percent": 0.0,
    "total_events_processed": 0,
    "events_processed_today": 0
  }
}
```

3. **Verify Health Check Performance**:
```bash
# Health checks should be fast (<10ms)
time curl -s http://localhost:8080/healthz > /dev/null
```

**Acceptance Criteria**:
- [ ] Health endpoint responds with HTTP 200 when healthy
- [ ] Response includes all required fields (status, timestamp, version, dependencies, metrics)
- [ ] Dependency status accurately reflects Pub/Sub connectivity
- [ ] Metrics provide meaningful operational information
- [ ] Health check response time <10ms
- [ ] Response format matches OpenAPI specification

---

### Scenario 5: Error Handling and Observability

**Objective**: Verify comprehensive error handling and logging

**Test Steps**:

1. **Test Invalid JSON Syntax**:
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"invalid": json syntax}'
```

2. **Test Oversized Payload**:
```bash
# Generate >1MB payload
python3 -c "
import json
large_payload = {
    'event_id': '123e4567-e89b-42d3-a456-426614174000',
    'event_timestamp': '2025-09-28T14:30:00.000Z',
    'event_source': 'quickstart-test',
    'event_type': 'test.error.payload_too_large',
    'event_version': '1.0.0',
    'payload': {'large_data': 'x' * 1048576}
}
print(json.dumps(large_payload))
" | curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d @-
```

3. **Verify Error Responses**:
```bash
# Check that errors return appropriate HTTP status codes
# Check that error messages are informative
# Check that trace IDs are included for correlation
```

4. **Verify Logging Output**:
```bash
# Check Cloud Logging for structured log entries
gcloud logging read "resource.type=cloud_function AND resource.labels.function_name=radar-signals-ingestion" \
  --limit=10 --format=json

# Verify log entries include:
# - Structured JSON format
# - Trace ID correlation
# - Error details for failed requests
# - Performance metrics
```

**Acceptance Criteria**:
- [ ] Invalid JSON returns HTTP 400 with parse error details
- [ ] Oversized payloads return HTTP 413 with size information
- [ ] All error responses include trace IDs
- [ ] Error messages are actionable and specific
- [ ] Structured logs generated for all requests
- [ ] No sensitive data exposed in error messages or logs

---

## 🔍 Performance Validation

### Latency Testing
```bash
# Measure end-to-end latency for 100 requests
for i in {1..100}; do
  time_start=$(date +%s.%N)
  curl -s -X POST http://localhost:8080/ \
    -H "Content-Type: application/json" \
    -d @examples/events/user-signup-completed.json > /dev/null
  time_end=$(date +%s.%N)
  latency=$(echo "($time_end - $time_start) * 1000" | bc -l)
  echo "$latency"
done | sort -n | awk '{p[NR] = $1} END {print "P50:", p[int(NR*0.5)], "P95:", p[int(NR*0.95)], "P99:", p[int(NR*0.99)]}'
```

**Target**: P95 latency <100ms

### Memory Usage Testing
```bash
# Monitor function memory usage during load
gcloud functions logs read radar-signals-ingestion \
  --limit=100 --format="value(textPayload)" | grep "Memory"
```

**Target**: Memory usage <100MB per concurrent request

## 🏛️ Constitutional Compliance Validation

### Data Governance Verification
- [ ] All events validated against canonical JSON schema
- [ ] Zero tolerance for schema violations (strict rejection)
- [ ] Schema validation errors provide specific field details
- [ ] No data transformation or business logic in ingestion layer

### Scalable Architecture Verification  
- [ ] Function deploys as serverless Cloud Function
- [ ] Auto-scaling from 0 to multiple concurrent instances
- [ ] Stateless operation (no persistent storage or connections)
- [ ] Async Pub/Sub publishing for event-driven architecture

### High Observability Verification
- [ ] Structured JSON logging for all operations
- [ ] Distributed tracing with trace ID propagation
- [ ] Health checks expose meaningful metrics
- [ ] Error correlation through trace IDs

### Modular Design Verification
- [ ] Clear separation of validation, publishing, and health concerns
- [ ] Reusable validation logic independent of transport
- [ ] Health checks independent of main processing flow
- [ ] Error handling modularized and consistent

### Phased Evolution Verification
- [ ] Function provides foundation for future intelligence layers
- [ ] Event format supports metadata for future enhancements
- [ ] Logging provides data for future ML/AI analysis
- [ ] Architecture allows for downstream processing additions

---

## ✅ Quickstart Completion Checklist

**Infrastructure Setup**:
- [ ] GCP project configured
- [ ] Pub/Sub topic created
- [ ] IAM permissions granted
- [ ] Local development environment ready

**Function Deployment**:
- [ ] Cloud Function deployed successfully
- [ ] Environment variables configured
- [ ] Function accessible via HTTPS endpoint
- [ ] Logging and monitoring enabled

**Validation Complete**:
- [ ] Scenario 1: Successful event ingestion ✅
- [ ] Scenario 2: Schema validation rejection ✅  
- [ ] Scenario 3: High-volume concurrent processing ✅
- [ ] Scenario 4: Health check validation ✅
- [ ] Scenario 5: Error handling and observability ✅

**Performance Targets Met**:
- [ ] P95 latency <100ms ✅
- [ ] Throughput >1000 events/second ✅
- [ ] Memory usage optimized ✅
- [ ] Error rate <0.1% ✅

**Constitutional Compliance**:
- [ ] All five constitutional principles verified ✅
- [ ] API contract specification compliance ✅
- [ ] Security requirements met ✅
- [ ] Observability standards achieved ✅

**Production Readiness**:
- [ ] All quickstart scenarios pass ✅
- [ ] Performance benchmarks met ✅
- [ ] Error handling comprehensive ✅
- [ ] Monitoring and alerting configured ✅

---

**Quickstart Status**: ✅ **Ready for Implementation Validation**

*Execute these scenarios after implementation to verify all specification requirements are met and the API is ready for production deployment.*