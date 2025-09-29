"""
T019 - Cloud Function main entry point

HTTP request routing with error handling and proper status codes.
Implements the serverless event ingestion API specification.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional, Union

import functions_framework
from flask import Request

from src.models.radar_signal import RadarSignalEvent
from src.models.errors import (
    APIError, ValidationAPIError, PayloadTooLargeError, 
    ServiceUnavailableError, RateLimitExceededError, ErrorType
)
from src.models.health import HealthResponse
from src.services.validator import validate_event
from src.services.publisher import publish_event
from src.services.health import get_health_status, record_request
from src.utils.logging import get_logger
from src.utils.config import get_config

# Initialize logging and configuration
logger = get_logger(__name__)
config = get_config()

# Type alias for Cloud Function response
CloudFunctionResponse = Union[
    Tuple[str, int],                    # (body, status_code)
    Tuple[str, int, Dict[str, str]]     # (body, status_code, headers)
]


def extract_trace_id(request: Request) -> str:
    """
    Extract or generate trace ID for request correlation.
    
    Args:
        request: Flask request object
        
    Returns:
        Trace ID string
    """
    # Check for existing trace ID in headers
    trace_id = request.headers.get('X-Trace-ID')
    
    if not trace_id:
        # Check Cloud Functions trace header
        trace_id = request.headers.get('X-Cloud-Trace-Context')
        if trace_id and '/' in trace_id:
            trace_id = trace_id.split('/')[0]  # Extract trace ID part
    
    if not trace_id:
        # Generate new trace ID
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    
    return trace_id


def validate_request_headers(request: Request) -> None:
    """
    Validate required request headers.
    
    Args:
        request: Flask request object
        
    Raises:
        ValidationAPIError: If headers are invalid
    """
    # Check Content-Type for POST requests
    if request.method == 'POST':
        content_type = request.headers.get('Content-Type', '')
        
        if not content_type:
            raise ValidationAPIError(
                message="Missing Content-Type header",
                details=[{
                    "field": "Content-Type",
                    "message": "Content-Type header is required for POST requests",
                    "expected_format": "application/json"
                }]
            )
        
        if not content_type.startswith('application/json'):
            raise ValidationAPIError(
                message="Invalid Content-Type header",
                details=[{
                    "field": "Content-Type",
                    "message": f"Expected 'application/json', got '{content_type}'",
                    "expected_format": "application/json"
                }]
            )


def validate_request_size(request: Request) -> None:
    """
    Validate request payload size.
    
    Args:
        request: Flask request object
        
    Raises:
        PayloadTooLargeError: If payload exceeds size limits
    """
    # Check Content-Length header
    content_length = request.headers.get('Content-Length')
    
    if content_length:
        try:
            size_bytes = int(content_length)
            max_size = config.max_payload_size
            
            if size_bytes > max_size:
                raise PayloadTooLargeError(size_bytes, max_size)
                
        except ValueError:
            # Invalid Content-Length header - let it proceed and fail during JSON parsing
            pass


def parse_json_request(request: Request, trace_id: str) -> Dict[str, Any]:
    """
    Parse and validate JSON request body.
    
    Args:
        request: Flask request object
        trace_id: Trace ID for logging
        
    Returns:
        Parsed JSON data
        
    Raises:
        ValidationAPIError: If JSON parsing fails
        PayloadTooLargeError: If payload is too large
    """
    try:
        # Get raw data for size checking
        raw_data = request.get_data()
        
        # Check actual payload size
        size_bytes = len(raw_data)
        max_size = config.max_payload_size
        
        if size_bytes > max_size:
            raise PayloadTooLargeError(size_bytes, max_size, trace_id)
        
        # Parse JSON
        json_data = request.get_json()
        
        if json_data is None:
            raise ValidationAPIError(
                message="Invalid JSON syntax in request body",
                details=[{
                    "field": "request_body",
                    "message": "Request body must contain valid JSON",
                    "code": "INVALID_JSON"
                }],
                trace_id=trace_id
            )
        
        logger.debug(
            "Request JSON parsed successfully",
            trace_id=trace_id,
            size_bytes=size_bytes,
            keys=list(json_data.keys()) if isinstance(json_data, dict) else None
        )
        
        return json_data
        
    except PayloadTooLargeError:
        raise  # Re-raise payload size errors
    except ValidationAPIError:
        raise  # Re-raise validation errors
    except Exception as e:
        logger.warning(
            "JSON parsing failed",
            trace_id=trace_id,
            error=str(e)
        )
        
        raise ValidationAPIError(
            message=f"JSON parsing error: {str(e)}",
            details=[{
                "field": "request_body",
                "message": str(e),
                "code": "INVALID_JSON"
            }],
            trace_id=trace_id
        )


def create_success_response(event: RadarSignalEvent, message_id: str, trace_id: str) -> CloudFunctionResponse:
    """
    Create successful event ingestion response.
    
    Args:
        event: Successfully processed RadarSignalEvent
        message_id: Pub/Sub message ID
        trace_id: Trace ID for correlation
        
    Returns:
        Cloud Function response tuple
    """
    response_data = {
        "status": "accepted",
        "event_id": str(event.event_id),
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "message_id": message_id
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Trace-ID": trace_id,
        "X-Message-ID": message_id
    }
    
    return json.dumps(response_data), 202, headers


def create_error_response(error: APIError) -> CloudFunctionResponse:
    """
    Create error response from API error.
    
    Args:
        error: APIError instance
        
    Returns:
        Cloud Function response tuple
    """
    response_data = error.to_dict()
    headers = error.get_headers()
    
    return json.dumps(response_data), error.status_code, headers


def handle_events_endpoint(request: Request, trace_id: str) -> CloudFunctionResponse:
    """
    Handle POST /events endpoint for radar signal ingestion.
    
    Args:
        request: Flask request object
        trace_id: Trace ID for correlation
        
    Returns:
        Cloud Function response tuple
    """
    start_time = time.time()
    
    try:
        logger.log_request_start("POST", "/", trace_id=trace_id)
        
        # Validate request headers
        validate_request_headers(request)
        
        # Validate request size
        validate_request_size(request)
        
        # Parse JSON request
        json_data = parse_json_request(request, trace_id)
        
        # Validate event against schema and create model
        radar_signal = validate_event(json_data, trace_id)
        
        # Publish to Pub/Sub
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        message_id = loop.run_until_complete(publish_event(radar_signal, trace_id))
        
        # Record successful request metrics
        latency_ms = (time.time() - start_time) * 1000
        record_request(latency_ms, success=True)
        
        # Log successful completion
        logger.log_request_end("POST", "/", 202, latency_ms, trace_id=trace_id,
                              event_id=str(radar_signal.event_id),
                              event_type=radar_signal.event_type,
                              message_id=message_id)
        
        return create_success_response(radar_signal, message_id, trace_id)
        
    except APIError as e:
        # Record failed request metrics
        latency_ms = (time.time() - start_time) * 1000
        record_request(latency_ms, success=False)
        
        # Ensure trace ID is set
        if not e.trace_id:
            e.trace_id = trace_id
        
        # Log error
        logger.log_request_end("POST", "/", e.status_code, latency_ms, trace_id=trace_id,
                              error_type=e.error_type.value,
                              error_message=e.message)
        
        return create_error_response(e)
        
    except Exception as e:
        # Handle unexpected errors
        latency_ms = (time.time() - start_time) * 1000
        record_request(latency_ms, success=False)
        
        logger.exception(
            "Unexpected error in events endpoint",
            trace_id=trace_id,
            latency_ms=latency_ms
        )
        
        # Create internal server error
        internal_error = APIError(
            error_type=ErrorType.INTERNAL_SERVER_ERROR,
            message="Internal server error occurred",
            trace_id=trace_id
        )
        
        logger.log_request_end("POST", "/", 500, latency_ms, trace_id=trace_id,
                              error_type="INTERNAL_SERVER_ERROR",
                              error_message="Unexpected error")
        
        return create_error_response(internal_error)


def handle_health_endpoint(request: Request, trace_id: str) -> CloudFunctionResponse:
    """
    Handle GET /healthz endpoint for service health monitoring.
    
    Args:
        request: Flask request object
        trace_id: Trace ID for correlation
        
    Returns:
        Cloud Function response tuple
    """
    start_time = time.time()
    
    try:
        logger.log_request_start("GET", "/healthz", trace_id=trace_id)
        
        # Get comprehensive health status
        health_status = get_health_status(use_cache=True)
        
        # Record request metrics
        latency_ms = (time.time() - start_time) * 1000
        record_request(latency_ms, success=True)
        
        # Create response
        response_data = health_status.to_dict()
        status_code = health_status.http_status_code
        
        headers = {
            "Content-Type": "application/json",
            "X-Trace-ID": trace_id
        }
        
        # Log completion
        logger.log_request_end("GET", "/healthz", status_code, latency_ms, trace_id=trace_id,
                              health_status=health_status.status.value,
                              dependency_count=len(health_status.dependencies))
        
        return json.dumps(response_data), status_code, headers
        
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        record_request(latency_ms, success=False)
        
        logger.exception(
            "Unexpected error in health endpoint",
            trace_id=trace_id,
            latency_ms=latency_ms
        )
        
        # Return basic unhealthy response
        error_response = {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "version": config.version,
            "dependencies": {},
            "metrics": {
                "uptime_seconds": 0,
                "requests_per_second": 0.0,
                "average_latency_ms": 0.0,
                "error_rate_percent": 100.0,
                "total_events_processed": 0,
                "events_processed_today": 0
            },
            "issues": [{
                "component": "health_service",
                "message": f"Health check failed: {str(e)}",
                "since": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "severity": "critical"
            }]
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Trace-ID": trace_id
        }
        
        logger.log_request_end("GET", "/healthz", 503, latency_ms, trace_id=trace_id,
                              error="Health check failed")
        
        return json.dumps(error_response), 503, headers


def main(request: Request) -> CloudFunctionResponse:
    """
    Main Cloud Function entry point.
    Routes requests to appropriate handlers based on method and path.
    
    Args:
        request: Flask request object from Cloud Functions runtime
        
    Returns:
        Cloud Function response tuple
    """
    # Extract trace ID for request correlation
    trace_id = extract_trace_id(request)
    
    try:
        # Route based on method and path
        if request.method == 'POST' and request.path in ['/', '/events']:
            return handle_events_endpoint(request, trace_id)
        
        elif request.method == 'GET' and request.path in ['/healthz', '/health']:
            return handle_health_endpoint(request, trace_id)
        
        else:
            # Method/path not allowed
            logger.warning(
                "Method or path not allowed",
                method=request.method,
                path=request.path,
                trace_id=trace_id
            )
            
            error = APIError(
                error_type=ErrorType.VALIDATION_FAILED,
                message=f"Method {request.method} not allowed for path {request.path}",
                trace_id=trace_id
            )
            
            return create_error_response(error)
            
    except Exception as e:
        # Ultimate fallback error handler
        logger.exception(
            "Critical error in main function",
            trace_id=trace_id,
            method=request.method,
            path=request.path
        )
        
        # Return basic error response
        error_response = {
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Critical server error occurred",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "retryable": True
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Trace-ID": trace_id
        }
        
        return json.dumps(error_response), 500, headers


# Register Cloud Function entry point
@functions_framework.http
def radar_signals_ingestion(request: Request) -> CloudFunctionResponse:
    """
    Cloud Functions entry point for radar signals event ingestion.
    
    Args:
        request: Flask request object
        
    Returns:
        HTTP response tuple
    """
    return main(request)


# For local testing and debugging
if __name__ == "__main__":
    import sys
    from flask import Flask
    
    app = Flask(__name__)
    
    @app.route('/', methods=['POST'])
    @app.route('/events', methods=['POST'])
    @app.route('/healthz', methods=['GET'])
    @app.route('/health', methods=['GET'])
    def local_handler():
        from flask import request
        response_data, status_code, *headers = main(request)
        
        if headers:
            response = app.response_class(
                response=response_data,
                status=status_code,
                headers=headers[0]
            )
        else:
            response = app.response_class(
                response=response_data,
                status=status_code,
                headers={"Content-Type": "application/json"}
            )
        
        return response
    
    # Run local development server
    print("Starting local development server...")
    print("POST /        - Event ingestion")
    print("GET  /healthz - Health check")
    print("Listening on http://localhost:8080")
    
    app.run(host='0.0.0.0', port=8080, debug=config.debug)