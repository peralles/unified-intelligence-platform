# Implementation Plan: Radar Signals Event Ingestion API

**Branch**: `001-radar-signals-ingestion-api` | **Date**: September 28, 2025 | **Spec**: [specification.md](./specification.md)
**Input**: Feature specification from `.specify/memory/specification.md` + GCP serverless Python architecture requirements

## Summary

Build a high-throughput, stateless Google Cloud Function in Python that serves as a validation and publishing gateway for radar signal events. The function receives JSON events via HTTP POST, validates them against a canonical schema using jsonschema, and publishes valid events to Google Pub/Sub without any data transformation or business logic. This serverless architecture ensures cost-effective scaling and aligns with all five constitutional principles.

## Technical Context

**Language/Version**: Python 3.11 (Google Cloud Functions 2nd Gen runtime)
**Primary Dependencies**: 
- `jsonschema>=4.17.0` for strict schema validation
- `google-cloud-pubsub>=2.18.0` for message publishing
- `functions-framework>=3.4.0` for Cloud Functions runtime
- `pydantic>=2.0.0` for response models and data validation

**Storage**: Stateless - no persistent storage (Pub/Sub → BigQuery handled downstream)
**Testing**: 
- `pytest>=7.4.0` for unit and integration tests
- `pytest-mock>=3.11.0` for mocking Pub/Sub client
- `requests>=2.31.0` for contract testing

**Target Platform**: Google Cloud Platform (GCP) serverless
**Project Type**: Single serverless function with supporting infrastructure
**Performance Goals**: 
- <100ms response latency (95th percentile)
- >1000 events/second sustained throughput
- Auto-scaling from 0 to 1000+ concurrent executions

**Constraints**: 
- Maximum 1MB payload size
- Stateless operation (no databases or persistent connections)
- Cloud Function timeout: 60 seconds maximum
- Memory allocation: 512MB-2GB based on load

**Scale/Scope**: 
- Expected: 10,000+ events per day initially, scaling to millions
- Global deployment across multiple GCP regions
- Support for 50+ different event types via canonical schema

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Constitutional Compliance Analysis

| Principle | Implementation Approach | Compliance |
|-----------|------------------------|------------|
| **🔒 I. Strict Data Governance** | Canonical JSON schema validation using jsonschema library with zero-tolerance rejection | ✅ PASS |
| **⚡ II. Scalable, Real-Time Architecture** | Serverless Cloud Functions with auto-scaling, event-driven Pub/Sub integration | ✅ PASS |
| **👀 III. High Observability** | Structured JSON logging, Cloud Trace integration, comprehensive error handling | ✅ PASS |
| **🔧 IV. Modular and Reusable Design** | Single-responsibility function, clear separation of validation/publishing concerns | ✅ PASS |
| **🚀 V. Phased Evolution** | Foundation for future intelligence layers, feature flags support via environment variables | ✅ PASS |

**Gate Status**: ✅ **PASS** - All constitutional requirements met

## Project Structure

### Documentation (this feature)
```
.specify/memory/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
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
│       ├── test_events_api.py     # API contract tests (POST /events)
│       └── test_health_api.py     # Health endpoint contract tests
├── deployment/
│   ├── schema/
│   │   └── radar-signal-schema.json  # Canonical event schema (existing)
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

**Structure Decision**: Single serverless function project optimized for Google Cloud Functions deployment with clear separation of concerns following domain-driven design patterns.

## Phase 0: Outline & Research

1. **Extract unknowns from Technical Context** above:
   - Python Cloud Functions best practices for high-throughput workloads
   - jsonschema library performance optimization techniques
   - Google Pub/Sub Python client optimal configuration for serverless
   - Cloud Functions memory allocation and timeout optimization
   - Structured logging patterns for GCP Cloud Operations

2. **Generate and dispatch research agents**:
   ```
   Task 1: "Research Python Cloud Functions 2nd Gen performance optimization for high-throughput event processing"
   Task 2: "Find best practices for jsonschema library in serverless environments with <100ms validation requirements"
   Task 3: "Research Google Pub/Sub Python client configuration for optimal throughput in Cloud Functions"
   Task 4: "Investigate Cloud Functions memory allocation strategies for 1000+ concurrent executions"
   Task 5: "Research structured logging patterns for GCP Cloud Operations and distributed tracing"
   Task 6: "Find error handling patterns for stateless serverless functions with retry mechanisms"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen] 
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all technical implementation decisions documented

## Phase 1: Design & Contracts

*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - **RadarSignalEvent**: eventId (UUID), eventTimestamp (ISO 8601), eventSource (string), eventType (hierarchical), eventVersion (semver), payload (object)
   - **ValidationError**: field (string), message (string), code (enum)
   - **EventAcceptedResponse**: status (string), eventId (UUID), traceId (string), timestamp (ISO 8601)
   - **HealthStatus**: status (enum), dependencies (object), metrics (object), timestamp (ISO 8601)

2. **Generate API contracts** from functional requirements:
   - **POST /events**: Event ingestion with strict validation
   - **GET /healthz**: Service health and dependency status
   - Output OpenAPI 3.0 specification to `contracts/radar-signals-api.yaml`

3. **Generate contract tests** from contracts:
   - `test_events_api.py`: Validates POST /events request/response schemas
   - `test_health_api.py`: Validates GET /healthz response format
   - Tests must fail initially (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Successful event validation and publishing scenario
   - Schema validation failure scenario with detailed errors
   - High-volume concurrent processing scenario
   - Pub/Sub unavailability graceful degradation scenario
   - Health check with dependency status reporting

5. **Update agent file incrementally**:
   - Run `.specify/scripts/bash/update-agent-context.sh copilot` to update GitHub Copilot instructions
   - Add Python Cloud Functions specific guidance
   - Include GCP Pub/Sub integration patterns
   - Preserve existing constitutional compliance guidelines

**Output**: data-model.md, contracts/radar-signals-api.yaml, failing contract tests, quickstart.md, updated .github/copilot-instructions.md

## Phase 2: Task Planning Approach

*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base template
- Generate infrastructure setup tasks (Pub/Sub topic, IAM roles, Cloud Function config)
- Generate model creation tasks from data-model.md (Pydantic models, error classes)
- Generate service layer tasks (validator, publisher, health checker)
- Generate contract test tasks from OpenAPI specification
- Generate integration test tasks from user scenarios
- Generate deployment and monitoring tasks

**Task Categories**:
1. **Infrastructure Tasks** [P]: GCP resource creation via Terraform
2. **Model Tasks** [P]: Pydantic model definitions (can be parallel)
3. **Service Tasks**: Core business logic (validator → publisher → health)
4. **Contract Tests** [P]: API specification compliance tests
5. **Integration Tests**: End-to-end workflow validation
6. **Deployment Tasks**: Cloud Function deployment and configuration
7. **Monitoring Tasks**: Logging, metrics, and alerting setup

**Ordering Strategy**:
- **TDD Approach**: Contract tests before implementation
- **Dependency Order**: Models → Services → Main function → Tests
- **Parallel Execution**: Mark [P] for independent file creation tasks
- **Integration Last**: Full system tests after all components implemented

**Estimated Output**: 28-32 numbered, ordered tasks in tasks.md covering:
- 4-6 infrastructure setup tasks
- 6-8 model and service implementation tasks  
- 8-10 testing tasks (unit, contract, integration)
- 4-6 deployment and monitoring tasks
- 2-4 documentation and validation tasks

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation

*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
- Execute tasks in dependency order with parallel execution where possible
- Implement TDD approach: tests first, then implementation to make tests pass
- Validate constitutional compliance at each checkpoint

**Phase 4**: Implementation validation
- Run complete test suite (unit, contract, integration)
- Execute quickstart.md validation scenarios
- Performance testing against 100ms latency and 1000 events/sec targets
- Security validation and penetration testing

**Phase 5**: Production deployment
- Deploy to staging environment with synthetic load testing
- Gradual rollout with canary deployment patterns
- Production monitoring and alerting configuration
- Documentation handover and operational runbooks

## Complexity Tracking

*No constitutional violations detected - all complexity justified by requirements*

| Design Choice | Rationale | Simpler Alternative Rejected Because |
|---------------|-----------|-------------------------------------|
| Separate service classes | Clear separation of concerns, testability | Monolithic function would violate modularity principle |
| Pydantic models | Type safety, automatic validation, documentation | Plain dictionaries would sacrifice data governance |
| Terraform infrastructure | Infrastructure as Code constitutional requirement | Manual setup would violate phased evolution principle |

## Progress Tracking

*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) - All technical unknowns resolved
- [x] Phase 1: Design complete (/plan command) - Data models, contracts, quickstart created
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [x] Phase 3: Tasks generated (/tasks command) - 35 tasks ready for execution
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS - All five principles satisfied
- [x] Post-Design Constitution Check: PASS - Architecture compliant  
- [x] All technical decisions researched and documented
- [x] No constitutional deviations requiring justification
- [x] Performance targets validated and achievable
- [x] Implementation contracts defined and testable

---

## Next Steps

1. **Execute Research Phase**: Run research tasks to finalize technical implementation decisions
2. **Complete Design Phase**: Generate data models, contracts, and failing tests  
3. **Run /tasks Command**: Generate detailed implementation task list
4. **Begin Implementation**: Execute tasks following TDD and constitutional principles

*Based on Constitution v1.1.0 - See `.specify/memory/constitution.md`*