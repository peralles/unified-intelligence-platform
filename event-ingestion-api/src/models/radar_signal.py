"""
T011 - RadarSignalEvent Pydantic model

Canonical radar signal event model enforcing strict data governance.
Implements complete Pydantic model from data-model.md with performance optimizations.
"""
from pydantic import BaseModel, Field, UUID4, field_validator, ConfigDict
from typing import Dict, Any, Optional
from datetime import datetime
import json
import uuid


class RadarSignalEvent(BaseModel):
    """
    Canonical radar signal event model enforcing strict data governance.
    Validates against the constitutional requirement for schema compliance.
    """
    
    model_config = ConfigDict(
        # Performance optimizations
        extra='forbid',  # No additional properties allowed
        frozen=False,    # Allow modification for processing
        str_strip_whitespace=True,  # Auto-strip whitespace
        validate_assignment=True,   # Validate on field assignment
        # Use camelCase aliases to match JSON schema
        alias_generator=None,  # We'll use explicit aliases
        # JSON schema generation
        json_schema_extra={
            "examples": [
                {
                    "eventId": "123e4567-e89b-42d3-a456-426614174000",
                    "eventTimestamp": "2025-09-28T14:30:00.000Z",
                    "eventSource": "user-management-service",
                    "eventType": "user.signup.completed",
                    "eventVersion": "1.0.0",
                    "payload": {
                        "user_id": "usr_789",
                        "email": "user@example.com",
                        "subscription": "premium"
                    }
                }
            ]
        }
    )
    
    event_id: UUID4 = Field(
        alias="eventId",
        description="Unique identifier for the specific event occurrence (UUID v4)",
        examples=["123e4567-e89b-42d3-a456-426614174000"]
    )
    
    event_timestamp: datetime = Field(
        alias="eventTimestamp", 
        description="ISO 8601 timestamp when the business event occurred",
        examples=["2025-09-28T14:30:00.000Z"]
    )
    
    event_source: str = Field(
        alias="eventSource",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-_.]*[a-zA-Z0-9]$",
        description="System or service that generated the event",
        examples=["user-management-service"]
    )
    
    event_type: str = Field(
        alias="eventType",
        min_length=1,
        max_length=200,
        pattern=r"^[a-zA-Z][a-zA-Z0-9-]*\.[a-zA-Z][a-zA-Z0-9-]*\.[a-zA-Z][a-zA-Z0-9-]*$",
        description="Hierarchical event classification (domain.entity.action)",
        examples=["user.signup.completed"]
    )
    
    event_version: str = Field(
        alias="eventVersion",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version of the event schema",
        examples=["1.0.0"]
    )
    
    payload: Dict[str, Any] = Field(
        min_length=1,  # At least 1 property required
        description="Business-specific event data conforming to event type schema",
        examples=[{"user_id": "usr_789", "email": "user@example.com"}]
    )

    @field_validator('event_timestamp')
    @classmethod
    def validate_timestamp_format(cls, v: datetime) -> datetime:
        """Ensure timestamp is in UTC and properly formatted."""
        if v.tzinfo is None:
            raise ValueError('Timestamp must include timezone information (use UTC with Z suffix)')
        return v

    @field_validator('payload')
    @classmethod
    def validate_payload_constraints(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payload size and property constraints."""
        if not v:
            raise ValueError('Payload must contain at least 1 property')
        
        if len(v) > 50:
            raise ValueError(f'Payload contains {len(v)} properties, maximum 50 allowed')
        
        # Check serialized size (1MB limit)
        try:
            payload_json = json.dumps(v, ensure_ascii=False)
            payload_size = len(payload_json.encode('utf-8'))
            if payload_size > 1048576:  # 1MB limit
                raise ValueError(f'Payload size {payload_size} bytes exceeds 1MB limit')
        except (TypeError, ValueError) as e:
            raise ValueError(f'Payload must be JSON serializable: {e}')
        
        return v

    @field_validator('event_id')
    @classmethod
    def validate_uuid_format(cls, v: UUID4) -> UUID4:
        """Validate UUID is version 4."""
        if isinstance(v, str):
            try:
                parsed_uuid = uuid.UUID(v)
                if parsed_uuid.version != 4:
                    raise ValueError(f'UUID must be version 4, got version {parsed_uuid.version}')
                return parsed_uuid
            except ValueError as e:
                raise ValueError(f'Invalid UUID format: {e}')
        
        if hasattr(v, 'version') and v.version != 4:
            raise ValueError(f'UUID must be version 4, got version {v.version}')
        
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization using camelCase field names."""
        return {
            "eventId": str(self.event_id),
            "eventTimestamp": self.event_timestamp.isoformat().replace('+00:00', 'Z'),
            "eventSource": self.event_source,
            "eventType": self.event_type,
            "eventVersion": self.event_version,
            "payload": self.payload
        }

    def to_json(self) -> str:
        """Convert to JSON string for Pub/Sub publishing."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RadarSignalEvent':
        """Create instance from dictionary with validation."""
        return cls(**data)

    def get_size_bytes(self) -> int:
        """Get serialized size in bytes."""
        return len(self.to_json().encode('utf-8'))

    def __str__(self) -> str:
        """String representation for logging."""
        return f"RadarSignalEvent(id={self.event_id}, type={self.event_type}, source={self.event_source})"

    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (f"RadarSignalEvent(event_id={self.event_id!r}, "
                f"event_timestamp={self.event_timestamp!r}, "
                f"event_source={self.event_source!r}, "
                f"event_type={self.event_type!r}, "
                f"event_version={self.event_version!r}, "
                f"payload_keys={list(self.payload.keys())!r})")


# Performance optimization: Pre-compile regex patterns
import re
_EVENT_SOURCE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-_.]*[a-zA-Z0-9]$")
_EVENT_TYPE_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*\.[a-zA-Z][a-zA-Z0-9-]*\.[a-zA-Z][a-zA-Z0-9-]*$")
_EVENT_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def validate_event_source_fast(source: str) -> bool:
    """Fast validation for event source format."""
    return bool(_EVENT_SOURCE_PATTERN.match(source))


def validate_event_type_fast(event_type: str) -> bool:
    """Fast validation for event type format."""
    return bool(_EVENT_TYPE_PATTERN.match(event_type))


def validate_event_version_fast(version: str) -> bool:
    """Fast validation for event version format."""
    return bool(_EVENT_VERSION_PATTERN.match(version))