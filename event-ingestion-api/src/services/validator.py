"""
T014 - JSON schema validation service

Pre-compiled jsonschema validator with <2ms performance target.
Integration with canonical schema and detailed error reporting.
"""
import json
import jsonschema
from functools import lru_cache
from typing import Dict, Any, List, Optional
from pathlib import Path
import time

from src.models.radar_signal import RadarSignalEvent
from src.models.errors import ValidationError, ValidationAPIError, create_validation_error
from src.utils.logging import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)


class ValidationService:
    """
    JSON schema validation service with performance optimization.
    Provides <2ms validation time using pre-compiled validators.
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize validation service with schema loading.
        
        Args:
            schema_path: Path to JSON schema file (optional, uses default)
        """
        self.schema_path = schema_path or self._get_default_schema_path()
        self._validator = None
        self._schema = None
        self.config = get_config()
    
    def _get_default_schema_path(self) -> str:
        """Get default path to radar signal schema."""
        # Get path relative to project root
        current_dir = Path(__file__).parent.parent.parent
        schema_path = current_dir / "deployment" / "schema" / "radar-signal-schema.json"
        return str(schema_path)
    
    @property
    def validator(self) -> jsonschema.protocols.Validator:
        """Get compiled JSON schema validator (cached for performance)."""
        if self._validator is None:
            self._validator = self._load_and_compile_schema()
        return self._validator
    
    @property
    def schema(self) -> Dict[str, Any]:
        """Get JSON schema dictionary (cached)."""
        if self._schema is None:
            self._schema = self._load_schema()
        return self._schema
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON schema from file."""
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            
            logger.debug(
                "JSON schema loaded successfully",
                schema_path=self.schema_path,
                schema_version=schema.get('definitions', {}).get('metadata', {}).get('version', 'unknown')
            )
            
            return schema
            
        except FileNotFoundError:
            raise ValueError(f"Schema file not found: {self.schema_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema file: {e}")
        except Exception as e:
            raise ValueError(f"Error loading schema: {e}")
    
    def _load_and_compile_schema(self) -> jsonschema.protocols.Validator:
        """Load and compile JSON schema for optimal performance."""
        schema = self._load_schema()
        
        try:
            # Use Draft 2020-12 validator for best error messages and performance
            validator_class = jsonschema.Draft202012Validator
            
            # Check schema validity
            validator_class.check_schema(schema)
            
            # Create compiled validator
            validator = validator_class(schema)
            
            logger.info(
                "JSON schema validator compiled successfully",
                schema_path=self.schema_path,
                validator_class=validator_class.__name__
            )
            
            return validator
            
        except jsonschema.SchemaError as e:
            raise ValueError(f"Invalid JSON schema: {e}")
        except Exception as e:
            raise ValueError(f"Error compiling schema: {e}")
    
    def validate_json_syntax(self, data: Any) -> Dict[str, Any]:
        """
        Validate JSON syntax and structure.
        
        Args:
            data: Data to validate (should be dict from JSON parsing)
            
        Returns:
            Validated data dictionary
            
        Raises:
            ValidationAPIError: If data is not valid JSON structure
        """
        if not isinstance(data, dict):
            raise ValidationAPIError(
                message="Request body must be a JSON object",
                details=[create_validation_error("request_body", "Expected JSON object, got " + type(data).__name__)]
            )
        
        if not data:
            raise ValidationAPIError(
                message="Request body cannot be empty",
                details=[create_validation_error("request_body", "Empty JSON object")]
            )
        
        return data
    
    def validate_against_schema(self, data: Dict[str, Any], trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate data against JSON schema.
        
        Args:
            data: Data to validate
            trace_id: Trace ID for logging correlation
            
        Returns:
            Validated data dictionary
            
        Raises:
            ValidationAPIError: If validation fails
        """
        start_time = time.time()
        
        try:
            # Validate against JSON schema
            validation_errors = list(self.validator.iter_errors(data))
            
            validation_time_ms = (time.time() - start_time) * 1000
            
            if validation_errors:
                # Convert jsonschema errors to our error format
                error_details = []
                for error in validation_errors:
                    field_path = ".".join(str(part) for part in error.absolute_path) if error.absolute_path else "root"
                    
                    validation_error = create_validation_error(
                        field=field_path,
                        message=error.message,
                        code="SCHEMA_VIOLATION"
                    )
                    error_details.append(validation_error)
                
                logger.log_event_validation(
                    event_id=data.get("event_id", "unknown"),
                    event_type=data.get("event_type", "unknown"),
                    validation_result="failed",
                    trace_id=trace_id,
                    validation_time_ms=validation_time_ms,
                    error_count=len(error_details)
                )
                
                raise ValidationAPIError(
                    message="Event validation failed against canonical schema",
                    details=error_details,
                    trace_id=trace_id
                )
            
            logger.log_event_validation(
                event_id=data.get("event_id", "unknown"),
                event_type=data.get("event_type", "unknown"),
                validation_result="success",
                trace_id=trace_id,
                validation_time_ms=validation_time_ms
            )
            
            # Performance monitoring
            if validation_time_ms > 5.0:  # Warn if validation takes >5ms
                logger.warning(
                    f"Schema validation took {validation_time_ms:.2f}ms (target: <2ms)",
                    trace_id=trace_id,
                    validation_time_ms=validation_time_ms,
                    performance_warning=True
                )
            
            return data
            
        except ValidationAPIError:
            raise  # Re-raise our validation errors
        except Exception as e:
            logger.exception(
                "Unexpected error during schema validation",
                trace_id=trace_id,
                validation_time_ms=(time.time() - start_time) * 1000
            )
            raise ValidationAPIError(
                message=f"Schema validation error: {str(e)}",
                details=[create_validation_error("schema_validation", str(e))],
                trace_id=trace_id
            )
    
    def validate_pydantic_model(self, data: Dict[str, Any], trace_id: Optional[str] = None) -> RadarSignalEvent:
        """
        Validate data using Pydantic model.
        
        Args:
            data: Data to validate
            trace_id: Trace ID for logging correlation
            
        Returns:
            Validated RadarSignalEvent instance
            
        Raises:
            ValidationAPIError: If Pydantic validation fails
        """
        start_time = time.time()
        
        try:
            # Create Pydantic model instance with validation
            radar_signal = RadarSignalEvent.model_validate(data)
            
            validation_time_ms = (time.time() - start_time) * 1000
            
            logger.debug(
                "Pydantic model validation successful",
                trace_id=trace_id,
                validation_time_ms=validation_time_ms,
                event_id=str(radar_signal.event_id),
                event_type=radar_signal.event_type
            )
            
            return radar_signal
            
        except Exception as e:
            validation_time_ms = (time.time() - start_time) * 1000
            
            # Convert Pydantic errors to our error format
            error_details = []
            
            if hasattr(e, 'errors'):  # Pydantic ValidationError
                for pydantic_error in e.errors():
                    field_path = ".".join(str(loc) for loc in pydantic_error['loc'])
                    
                    validation_error = create_validation_error(
                        field=field_path,
                        message=pydantic_error['msg'],
                        code=pydantic_error['type']
                    )
                    error_details.append(validation_error)
            else:
                # Other exceptions
                error_details.append(create_validation_error("pydantic_validation", str(e)))
            
            logger.log_event_validation(
                event_id=data.get("event_id", "unknown"),
                event_type=data.get("event_type", "unknown"),
                validation_result="failed",
                trace_id=trace_id,
                validation_time_ms=validation_time_ms,
                validation_stage="pydantic",
                error_count=len(error_details)
            )
            
            raise ValidationAPIError(
                message="Pydantic model validation failed",
                details=error_details,
                trace_id=trace_id
            )
    
    def validate_event(self, data: Any, trace_id: Optional[str] = None) -> RadarSignalEvent:
        """
        Complete event validation pipeline.
        
        Args:
            data: Raw data to validate
            trace_id: Trace ID for logging correlation
            
        Returns:
            Validated RadarSignalEvent instance
            
        Raises:
            ValidationAPIError: If any validation step fails
        """
        start_time = time.time()
        
        try:
            # Step 1: JSON structure validation
            json_data = self.validate_json_syntax(data)
            
            # Step 2: JSON schema validation
            schema_validated_data = self.validate_against_schema(json_data, trace_id)
            
            # Step 3: Pydantic model validation
            radar_signal = self.validate_pydantic_model(schema_validated_data, trace_id)
            
            total_validation_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                "Event validation completed successfully",
                trace_id=trace_id,
                total_validation_time_ms=total_validation_time_ms,
                event_id=str(radar_signal.event_id),
                event_type=radar_signal.event_type,
                event_source=radar_signal.event_source
            )
            
            return radar_signal
            
        except ValidationAPIError:
            total_validation_time_ms = (time.time() - start_time) * 1000
            logger.error(
                "Event validation failed",
                trace_id=trace_id,
                total_validation_time_ms=total_validation_time_ms
            )
            raise
        except Exception as e:
            total_validation_time_ms = (time.time() - start_time) * 1000
            logger.exception(
                "Unexpected error during event validation",
                trace_id=trace_id,
                total_validation_time_ms=total_validation_time_ms
            )
            raise ValidationAPIError(
                message=f"Validation pipeline error: {str(e)}",
                details=[create_validation_error("validation_pipeline", str(e))],
                trace_id=trace_id
            )
    
    def get_schema_version(self) -> str:
        """Get schema version information."""
        try:
            metadata = self.schema.get('definitions', {}).get('metadata', {})
            return metadata.get('version', '1.0.0')
        except Exception:
            return '1.0.0'
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation performance statistics."""
        return {
            'schema_path': self.schema_path,
            'schema_version': self.get_schema_version(),
            'validator_class': type(self.validator).__name__,
            'schema_loaded': self._schema is not None,
            'validator_compiled': self._validator is not None
        }


# Global validator instance for performance
_global_validator: Optional[ValidationService] = None


@lru_cache(maxsize=1)
def get_validator() -> ValidationService:
    """
    Get global validation service instance.
    Cached for performance - avoids recompiling schema.
    
    Returns:
        ValidationService instance
    """
    global _global_validator
    
    if _global_validator is None:
        _global_validator = ValidationService()
    
    return _global_validator


def validate_event(data: Any, trace_id: Optional[str] = None) -> RadarSignalEvent:
    """
    Validate event using global validator instance.
    
    Args:
        data: Raw data to validate
        trace_id: Trace ID for logging correlation
        
    Returns:
        Validated RadarSignalEvent instance
        
    Raises:
        ValidationAPIError: If validation fails
    """
    return get_validator().validate_event(data, trace_id)