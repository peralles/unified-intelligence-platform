"""
T017 - Structured logging utility

JSON formatter for Cloud Operations integration with trace ID correlation.
Supports constitutional requirement for high observability.
"""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
import traceback
import os


class StructuredLogger:
    """
    Structured logging utility for Cloud Operations integration.
    Provides JSON-formatted logs with trace correlation and structured fields.
    """
    
    def __init__(self, logger_name: Optional[str] = None, log_level: str = "INFO"):
        """
        Initialize structured logger.
        
        Args:
            logger_name: Name for the logger (defaults to __name__)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger_name = logger_name or __name__
        self.logger = logging.getLogger(self.logger_name)
        
        # Configure log level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(numeric_level)
        
        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create console handler with JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self._create_json_formatter())
        self.logger.addHandler(handler)
        
        # Prevent duplicate logs from parent loggers
        self.logger.propagate = False
        
        # Store project ID for Cloud Trace integration
        self.project_id = os.environ.get('PROJECT_ID', 'unified-intelligence-platform')

    def _create_json_formatter(self) -> logging.Formatter:
        """Create JSON formatter for structured logging."""
        return JsonFormatter()

    def _create_log_entry(
        self,
        level: str,
        message: str,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create structured log entry.
        
        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            trace_id: Distributed trace ID for correlation
            **kwargs: Additional structured fields
            
        Returns:
            Structured log entry dictionary
        """
        # Base log entry with required fields
        log_entry = {
            "severity": level.upper(),
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": self.logger_name
        }
        
        # Add trace information for Cloud Operations correlation
        if trace_id:
            log_entry["logging.googleapis.com/trace"] = f"projects/{self.project_id}/traces/{trace_id}"
            log_entry["trace_id"] = trace_id
        
        # Add structured fields
        log_entry.update(kwargs)
        
        return log_entry

    def debug(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log debug message."""
        self._log("DEBUG", message, trace_id, **kwargs)

    def info(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log info message."""
        self._log("INFO", message, trace_id, **kwargs)

    def warning(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log warning message."""
        self._log("WARNING", message, trace_id, **kwargs)

    def error(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log error message."""
        self._log("ERROR", message, trace_id, **kwargs)

    def critical(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log critical message."""
        self._log("CRITICAL", message, trace_id, **kwargs)

    def exception(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log exception with traceback."""
        # Add exception information
        kwargs["exception_type"] = type(sys.exc_info()[1]).__name__ if sys.exc_info()[1] else None
        kwargs["exception_message"] = str(sys.exc_info()[1]) if sys.exc_info()[1] else None
        kwargs["traceback"] = traceback.format_exc() if sys.exc_info()[0] else None
        
        self._log("ERROR", message, trace_id, **kwargs)

    def _log(self, level: str, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Internal logging method."""
        log_entry = self._create_log_entry(level, message, trace_id, **kwargs)
        
        # Use appropriate logging level
        numeric_level = getattr(logging, level.upper())
        
        try:
            self.logger.log(numeric_level, json.dumps(log_entry, ensure_ascii=False, default=str))
        except (TypeError, ValueError) as e:
            # Fallback for non-serializable objects
            safe_log_entry = {
                "severity": level.upper(),
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "logger": self.logger_name,
                "serialization_error": str(e)
            }
            if trace_id:
                safe_log_entry["trace_id"] = trace_id
            
            self.logger.log(numeric_level, json.dumps(safe_log_entry, ensure_ascii=False, default=str))

    def log_request_start(
        self,
        method: str,
        path: str,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log HTTP request start."""
        self.info(
            f"Request started: {method} {path}",
            trace_id=trace_id,
            http_method=method,
            http_path=path,
            request_phase="start",
            **kwargs
        )

    def log_request_end(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log HTTP request completion."""
        level = "ERROR" if status_code >= 500 else "WARNING" if status_code >= 400 else "INFO"
        
        self._log(
            level,
            f"Request completed: {method} {path} - {status_code} ({latency_ms:.2f}ms)",
            trace_id=trace_id,
            http_method=method,
            http_path=path,
            http_status_code=status_code,
            latency_ms=latency_ms,
            request_phase="end",
            **kwargs
        )

    def log_event_validation(
        self,
        event_id: str,
        event_type: str,
        validation_result: str,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log event validation result."""
        level = "ERROR" if validation_result == "failed" else "INFO"
        
        self._log(
            level,
            f"Event validation {validation_result}: {event_type}",
            trace_id=trace_id,
            event_id=event_id,
            event_type=event_type,
            validation_result=validation_result,
            operation="event_validation",
            **kwargs
        )

    def log_pubsub_publish(
        self,
        event_id: str,
        topic_name: str,
        message_id: Optional[str],
        success: bool,
        latency_ms: float,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log Pub/Sub publish result."""
        level = "ERROR" if not success else "INFO"
        status = "success" if success else "failed"
        
        self._log(
            level,
            f"Pub/Sub publish {status}: {topic_name} ({latency_ms:.2f}ms)",
            trace_id=trace_id,
            event_id=event_id,
            pubsub_topic=topic_name,
            pubsub_message_id=message_id,
            pubsub_success=success,
            latency_ms=latency_ms,
            operation="pubsub_publish",
            **kwargs
        )

    def log_health_check(
        self,
        status: str,
        dependencies: Dict[str, str],
        trace_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log health check result."""
        level = "ERROR" if status == "unhealthy" else "WARNING" if status == "degraded" else "INFO"
        
        self._log(
            level,
            f"Health check completed: {status}",
            trace_id=trace_id,
            health_status=status,
            dependencies=dependencies,
            operation="health_check",
            **kwargs
        )


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Handles conversion of log records to JSON format.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        try:
            # If message is already JSON (from StructuredLogger), return as-is
            if hasattr(record, 'msg') and isinstance(record.msg, str):
                try:
                    json.loads(record.msg)  # Validate JSON
                    return record.msg
                except (json.JSONDecodeError, ValueError):
                    pass
            
            # Create structured log entry for non-JSON messages
            log_entry = {
                "severity": record.levelname,
                "message": record.getMessage(),
                "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # Add exception information if present
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            
            return json.dumps(log_entry, ensure_ascii=False)
            
        except Exception as e:
            # Fallback to simple format if JSON formatting fails
            return f'{{"severity": "ERROR", "message": "Logging error: {str(e)}", "original_message": "{record.getMessage()}"}}'


# Global logger instance
_global_logger: Optional[StructuredLogger] = None


def get_logger(logger_name: Optional[str] = None, log_level: Optional[str] = None) -> StructuredLogger:
    """
    Get global structured logger instance.
    
    Args:
        logger_name: Name for the logger
        log_level: Logging level override
        
    Returns:
        StructuredLogger instance
    """
    global _global_logger
    
    if _global_logger is None:
        # Get log level from environment or use INFO as default
        default_log_level = os.environ.get('LOG_LEVEL', 'INFO')
        _global_logger = StructuredLogger(
            logger_name=logger_name,
            log_level=log_level or default_log_level
        )
    
    return _global_logger


def configure_logging(log_level: str = "INFO", project_id: Optional[str] = None) -> None:
    """
    Configure global logging settings.
    
    Args:
        log_level: Global log level
        project_id: GCP project ID for trace correlation
    """
    global _global_logger
    
    if project_id:
        os.environ['PROJECT_ID'] = project_id
    
    _global_logger = StructuredLogger(log_level=log_level)


# Convenience functions using global logger

def debug(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log debug message using global logger."""
    get_logger().debug(message, trace_id, **kwargs)


def info(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log info message using global logger."""
    get_logger().info(message, trace_id, **kwargs)


def warning(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log warning message using global logger."""
    get_logger().warning(message, trace_id, **kwargs)


def error(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log error message using global logger."""
    get_logger().error(message, trace_id, **kwargs)


def critical(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log critical message using global logger."""
    get_logger().critical(message, trace_id, **kwargs)


def exception(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log exception with traceback using global logger."""
    get_logger().exception(message, trace_id, **kwargs)