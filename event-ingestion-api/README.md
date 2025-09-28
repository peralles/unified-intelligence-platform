# Radar Signals Event Ingestion API

> **High-throughput, scalable API for real-time ingestion of business events into the Unified Data Intelligence Platform**

[![Constitutional Compliance](https://img.shields.io/badge/Constitutional-Compliant-green)](../.specify/memory/constitution.md)
[![Phase](https://img.shields.io/badge/Phase-1%20MVP-blue)](../.specify/memory/constitution.md#evolution-roadmap)
[![API Version](https://img.shields.io/badge/API-v1.0.0-blue)](./deployment/openapi-spec.yaml)
[![Schema Version](https://img.shields.io/badge/Schema-v1.0.0-blue)](./deployment/schema/radar-signal-schema.json)

## 🎯 Purpose

The Radar Signals Event Ingestion API serves as the **foundational entry point** for the Unified Data Intelligence Platform's Phase 1 MVP. It captures standardized business events from diverse internal and external sources, enabling the organization to evolve from intuition-based reactions to **data-driven, autonomous operations**.

### Key Capabilities

- **📥 Event Ingestion**: POST /events endpoint for radar signal submission
- **🔍 Strict Validation**: Canonical JSON schema enforcement with zero tolerance
- **🚀 Asynchronous Publishing**: Immediate Pub/Sub routing without business logic
- **💖 Health Monitoring**: GET /healthz endpoint for operational visibility
- **⚡ High Performance**: Sub-100ms response time, 1000+ events/second throughput

## 🏛️ Constitutional Alignment

This API strictly adheres to all [Five Constitutional Principles](../CONSTITUTION.md):

| Principle | Implementation |
|-----------|----------------|
| **🔒 Strict Data Governance** | Canonical RadarSignal schema validation, zero schema drift tolerance |
| **⚡ Scalable Architecture** | Serverless Cloud Functions, auto-scaling Pub/Sub integration |
| **👀 High Observability** | Structured logging, distributed tracing, comprehensive metrics |
| **🔧 Modular Design** | Clear separation: validation → publishing → response |
| **🚀 Phased Evolution** | Foundation for future intelligence and automation layers |

## 📋 Specification

**📖 Complete Specification**: [`.specify/memory/specification.md`](./.specify/memory/specification.md)

### Core Requirements

- **Canonical Schema**: All events MUST conform to the [RadarSignal schema](./deployment/schema/radar-signal-schema.json)
- **Immediate Validation**: 100% of events validated before processing
- **Asynchronous Processing**: No business logic, pure ingestion and routing
- **Error Transparency**: Detailed validation errors for non-compliant events
- **High Reliability**: 99.9% availability with graceful degradation

### API Contract

**📋 OpenAPI Specification**: [`deployment/openapi-spec.yaml`](./deployment/openapi-spec.yaml)

#### RadarSignal Event Format

```json
{
  "eventId": "123e4567-e89b-12d3-a456-426614174000",
  "eventTimestamp": "2025-09-28T14:30:00.000Z",
  "eventSource": "user-management-service",
  "eventType": "user.signup.completed", 
  "eventVersion": "1.0.0",
  "payload": {
    "userId": "usr_789",
    "email": "user@example.com",
    "subscription": "premium"
  }
}
```

#### Response Examples

**✅ Success (202 Accepted)**:
```json
{
  "status": "accepted",
  "eventId": "123e4567-e89b-12d3-a456-426614174000",
  "traceId": "trace_abc123def456",
  "timestamp": "2025-09-28T14:30:00.123Z"
}
```

**❌ Validation Error (400 Bad Request)**:
```json
{
  "error": "VALIDATION_FAILED",
  "message": "Event validation failed",
  "details": [
    {
      "field": "eventTimestamp",
      "message": "Invalid ISO 8601 timestamp format"
    }
  ],
  "traceId": "trace_def456ghi789",
  "timestamp": "2025-09-28T14:30:00.123Z"
}
```

## 🛠️ Technology Stack

Following the [Development Guidelines](../.github/copilot-instructions.md):

- **Runtime**: Go 1.21+ (Google Cloud Functions 2nd generation)
- **Schema Validation**: github.com/xeipuuv/gojsonschema v1.2.0+
- **Messaging**: Google Cloud Pub/Sub Go client library
- **Platform**: Google Cloud Platform (serverless architecture)
- **Testing**: Go standard testing + testify assertions
- **Deployment**: Cloud Functions with optional Terraform IaC

## 📁 Project Structure

```
event-ingestion-api/
├── .specify/
│   └── memory/
│       ├── specification.md      # Complete functional specification
│       └── constitution.md       # Constitutional compliance guidelines
├── deployment/
│   ├── schema/
│   │   └── radar-signal-schema.json  # Canonical event schema
│   ├── openapi-spec.yaml            # API contract specification
│   ├── function.yaml               # Cloud Functions config
│   └── terraform/                  # Infrastructure as Code (optional)
├── examples/
│   ├── events/                     # Sample event payloads
│   └── responses/                  # Example API responses
├── src/                           # Go source code (to be implemented)
├── tests/                         # Test suites (to be implemented)
└── README.md                      # This file
```

## 🚀 Quick Start

### Testing with Examples

```bash
# Test valid event
curl -X POST https://your-api-url/events \
  -H "Content-Type: application/json" \
  -d @examples/events/user-signup-completed.json

# Check health status  
curl https://your-api-url/healthz

# Test validation error
curl -X POST https://your-api-url/events \
  -H "Content-Type: application/json" \
  -d @examples/events/invalid-missing-fields.json
```

### Schema Validation

```bash
# Validate event against canonical schema (when implemented)
go run cmd/validate/main.go < examples/events/user-signup-completed.json
```

## 📊 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Response Time** | <100ms (95th percentile) | End-to-end API response |
| **Throughput** | >1,000 events/second | Sustained concurrent load |
| **Availability** | 99.9% | Monthly uptime SLA |
| **Error Rate** | <0.1% | Invalid events excluded |
| **Scaling** | Zero to peak | Auto-scaling from cold start |

## 🔍 Monitoring & Observability

### Health Check Endpoint
- **GET /healthz**: Service and dependency health status
- **Metrics**: Uptime, request rate, latency, error rates
- **Dependencies**: Pub/Sub connectivity, schema registry status

### Structured Logging
- **Format**: JSON with consistent field names
- **Trace IDs**: Request correlation across services  
- **Events**: Validation results, publish status, errors

### Key Metrics
- Events processed per second
- Validation failure rate by error type
- Pub/Sub publishing latency
- Schema compliance percentage

## 🧪 Testing Strategy

### Test Categories (To Be Implemented)
- **Contract Tests**: API specification compliance
- **Unit Tests**: Validation logic, error handling
- **Integration Tests**: End-to-end with Pub/Sub
- **Performance Tests**: Load testing, latency validation
- **Schema Tests**: Canonical schema compliance

### Constitutional Compliance Testing
```bash
# Run constitutional compliance check
make constitutional-check

# Validate specific principles
make enforce-governance     # Schema validation compliance
make enforce-architecture   # Serverless architecture validation
```

## 🔐 Security Considerations

- **Input Validation**: Strict schema enforcement prevents malformed data
- **Rate Limiting**: Protection against abuse and resource exhaustion  
- **Request Size Limits**: 1MB maximum payload size
- **Error Information**: Detailed validation errors without sensitive data exposure
- **Dependency Security**: Secure Pub/Sub communication with proper authentication

## 📈 Roadmap Integration

This API serves as the foundation for the platform's evolution:

- **Phase 1 (Current)**: Basic event ingestion with schema validation
- **Phase 2**: Integration with intelligent pattern detection
- **Phase 3**: Historical analysis and contextual enrichment  
- **Phase 4**: AI-driven autonomous action triggers

## 🤝 Contributing

1. **Constitutional Compliance**: All changes must adhere to the [platform constitution](../CONSTITUTION.md)
2. **Schema Governance**: Changes to RadarSignal schema require formal approval
3. **Testing Requirements**: Maintain 80%+ code coverage
4. **Performance Standards**: New features must meet latency and throughput targets

## 📚 Related Documentation

- **[Platform Constitution](../CONSTITUTION.md)** - Foundational principles
- **[Full Specification](./.specify/memory/specification.md)** - Complete requirements
- **[OpenAPI Contract](./deployment/openapi-spec.yaml)** - API specification
- **[Canonical Schema](./deployment/schema/radar-signal-schema.json)** - Event data model
- **[Development Guidelines](../.github/copilot-instructions.md)** - Implementation guidance

---

**Version**: 1.0.0 | **Status**: Specified, Ready for Implementation | **Phase**: 1 MVP