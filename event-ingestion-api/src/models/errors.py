"""
T012 - Error response models

Custom exception classes and error response models with structured error handling.
Supports constitutional requirement for high observability.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum
import uuid


class ErrorType(str, Enum):
    """Error type enumeration for consistent error classification."""
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"

    @property
    def http_status_code(self) -> int:
        """Get HTTP status code for error type."""
        status_codes = {
            self.VALIDATION_FAILED: 400,
            self.PAYLOAD_TOO_LARGE: 413,
            self.RATE_LIMIT_EXCEEDED: 429,
            self.SERVICE_UNAVAILABLE: 503,
            self.INTERNAL_SERVER_ERROR: 500
        }
        return status_codes[self]

    @property
    def is_retryable(self) -> bool:
        """Check if error type is retryable."""
        retryable_errors = {
            self.RATE_LIMIT_EXCEEDED,
            self.SERVICE_UNAVAILABLE,
            self.INTERNAL_SERVER_ERROR
        }
        return self in retryable_errors


class ValidationError(BaseModel):
    """
    Individual field validation error with specific failure details.
    Supports constitutional requirement for high observability.
    """
    
    model_config = ConfigDict(
        extra='forbid',
        frozen=True  # Immutable error details
    )
    
    field: str = Field(
        description="JSON path to the field that failed validation",
        examples=["event_timestamp", "payload.email"]
    )
    
    message: str = Field(
        description="Human-readable validation error message",
        examples=["Invalid ISO 8601 timestamp format"]
    )
    
    code: Optional[str] = Field(
        None,
        description="Machine-readable error code for automated handling",
        examples=["INVALID_FORMAT", "MISSING_FIELD", "VALUE_TOO_LARGE"]
    )
    
    expected_format: Optional[str] = Field(
        None,
        description="Expected format or pattern for the field",
        examples=["YYYY-MM-DDTHH:MM:SS.sssZ", "UUID v4", "domain.entity.action"]
    )

    def __str__(self) -> str:
        """String representation for logging."""
        return f"ValidationError(field={self.field}, message={self.message})"


class EventAcceptedResponse(BaseModel):
    """
    Success response confirming event acceptance and queuing.
    Includes tracing information for end-to-end observability.
    """
    
    model_config = ConfigDict(
        extra='forbid'
    )
    
    status: str = Field(
        default="accepted",
        description="Confirmation status - always 'accepted' for successful ingestion"
    )
    
    event_id: str = Field(
        description="Echo of submitted event ID for correlation",
        examples=["123e4567-e89b-42d3-a456-426614174000"]
    )
    
    trace_id: str = Field(
        description="Unique trace identifier for request tracking",
        examples=["trace_abc123def456ghi789"]
    )
    
    timestamp: datetime = Field(
        description="Server timestamp when response was generated"
    )
    
    message_id: Optional[str] = Field(
        None,
        description="Pub/Sub message ID for downstream tracking",
        examples=["1234567890123456"]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "status": self.status,
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat().replace('+00:00', 'Z')
        }
        if self.message_id:
            result["message_id"] = self.message_id
        return result


class ErrorResponse(BaseModel):
    """
    Comprehensive error response supporting constitutional observability requirements.
    Provides actionable information for client retry logic.
    """
    
    model_config = ConfigDict(
        extra='forbid'
    )
    
    error: ErrorType = Field(
        description="Machine-readable error type classification"
    )
    
    message: str = Field(
        description="Human-readable error summary",
        examples=["Event validation failed against canonical schema"]
    )
    
    details: Optional[List[ValidationError]] = Field(
        None,
        description="Specific validation failure details (for VALIDATION_FAILED errors)"
    )
    
    trace_id: str = Field(
        description="Unique trace identifier for error correlation"
    )
    
    timestamp: datetime = Field(
        description="Server timestamp when error occurred"
    )
    
    retryable: bool = Field(
        description="Whether the client should retry this request"
    )
    
    retry_after: Optional[int] = Field(
        None,
        description="Seconds to wait before retrying (for rate limiting)",
        ge=1  # Must be at least 1 second
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "error": self.error.value,
            "message": self.message,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat().replace('+00:00', 'Z'),
            "retryable": self.retryable
        }
        
        if self.details:
            result["details"] = [detail.model_dump() for detail in self.details]
        
        if self.retry_after is not None:
            result["retry_after"] = self.retry_after
        
        return result

    @property
    def http_status_code(self) -> int:
        """Get HTTP status code for this error."""
        return self.error.http_status_code

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for error response."""
        headers = {
            "Content-Type": "application/json",
            "X-Trace-ID": self.trace_id
        }
        
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        
        if self.error == ErrorType.RATE_LIMIT_EXCEEDED:
            # Add rate limiting headers if available
            headers["X-RateLimit-Limit"] = "1000"  # Could be configurable
            headers["X-RateLimit-Remaining"] = "0"
        
        return headers


# Custom Exception Classes

class APIError(Exception):
    """
    Base API error class with structured error information.
    Supports constitutional requirement for comprehensive error handling.
    """
    
    def __init__(
        self, 
        error_type: ErrorType, 
        message: str, 
        details: Optional[List[ValidationError]] = None,
        trace_id: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        self.error_type = error_type
        self.message = message
        self.details = details or []
        self.trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()
        super().__init__(message)
    
    @property
    def status_code(self) -> int:
        """Get HTTP status code for this error."""
        return self.error_type.http_status_code
    
    @property
    def retryable(self) -> bool:
        """Check if this error is retryable."""
        return self.error_type.is_retryable

    def to_error_response(self) -> ErrorResponse:
        """Convert to ErrorResponse model."""
        return ErrorResponse(
            error=self.error_type,
            message=self.message,
            details=self.details,
            trace_id=self.trace_id,
            timestamp=self.timestamp,
            retryable=self.retryable,
            retry_after=self.retry_after
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return self.to_error_response().to_dict()

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for error response."""
        return self.to_error_response().get_headers()

    def __str__(self) -> str:
        """String representation for logging."""
        return f"APIError({self.error_type.value}: {self.message})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (f"APIError(error_type={self.error_type!r}, "
                f"message={self.message!r}, "
                f"trace_id={self.trace_id!r}, "
                f"details_count={len(self.details)})")


class ValidationAPIError(APIError):
    """Specific error for validation failures."""
    
    def __init__(self, message: str, details: List[ValidationError], trace_id: Optional[str] = None):
        super().__init__(
            error_type=ErrorType.VALIDATION_FAILED,
            message=message,
            details=details,
            trace_id=trace_id
        )


class PayloadTooLargeError(APIError):
    """Specific error for oversized payloads."""
    
    def __init__(self, size_bytes: int, max_size_bytes: int = 1048576, trace_id: Optional[str] = None):
        message = f"Payload size {size_bytes} bytes exceeds maximum limit of {max_size_bytes} bytes"
        super().__init__(
            error_type=ErrorType.PAYLOAD_TOO_LARGE,
            message=message,
            trace_id=trace_id
        )


class ServiceUnavailableError(APIError):
    """Specific error for service unavailability."""
    
    def __init__(self, message: str, retry_after: int = 30, trace_id: Optional[str] = None):
        super().__init__(
            error_type=ErrorType.SERVICE_UNAVAILABLE,
            message=message,
            trace_id=trace_id,
            retry_after=retry_after
        )


class RateLimitExceededError(APIError):
    """Specific error for rate limit violations."""
    
    def __init__(self, message: str, retry_after: int = 60, trace_id: Optional[str] = None):
        super().__init__(
            error_type=ErrorType.RATE_LIMIT_EXCEEDED,
            message=message,
            trace_id=trace_id,
            retry_after=retry_after
        )


# Utility functions for error creation

def create_validation_error(field: str, message: str, code: Optional[str] = None, expected_format: Optional[str] = None) -> ValidationError:
    """Create a validation error with consistent formatting."""
    return ValidationError(
        field=field,
        message=message,
        code=code,
        expected_format=expected_format
    )


def create_validation_api_error(errors: List[ValidationError], trace_id: Optional[str] = None) -> ValidationAPIError:
    """Create a validation API error from multiple validation errors."""
    if not errors:
        raise ValueError("At least one validation error is required")
    
    message = "Event validation failed against canonical schema"
    if len(errors) == 1:
        message = f"Event validation failed: {errors[0].message}"
    
    return ValidationAPIError(
        message=message,
        details=errors,
        trace_id=trace_id
    )