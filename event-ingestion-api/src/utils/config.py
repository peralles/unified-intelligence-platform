"""
T018 - Environment configuration

Environment variable handling with defaults and validation.
GCP project and Pub/Sub topic configuration for serverless deployment.
"""
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Config:
    """
    Application configuration with environment variable handling.
    Immutable configuration object with validation and defaults.
    """
    
    # Google Cloud Platform Configuration
    project_id: str
    pubsub_topic: str
    
    # Performance Configuration
    max_payload_size: int
    validation_timeout: int
    publish_timeout: int
    
    # Logging Configuration
    log_level: str
    structured_logging: bool
    
    # Application Configuration
    environment: str
    debug: bool
    version: str
    
    # Optional Development Configuration
    google_application_credentials: Optional[str] = None
    pubsub_emulator_host: Optional[str] = None
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == 'production'
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == 'development'
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == 'testing'
    
    @property
    def use_emulator(self) -> bool:
        """Check if using Pub/Sub emulator."""
        return self.pubsub_emulator_host is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'project_id': self.project_id,
            'pubsub_topic': self.pubsub_topic,
            'max_payload_size': self.max_payload_size,
            'validation_timeout': self.validation_timeout,
            'publish_timeout': self.publish_timeout,
            'log_level': self.log_level,
            'structured_logging': self.structured_logging,
            'environment': self.environment,
            'debug': self.debug,
            'version': self.version,
            'google_application_credentials': self.google_application_credentials,
            'pubsub_emulator_host': self.pubsub_emulator_host
        }


def _get_env_var(key: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Get environment variable with validation.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        required: Whether the variable is required
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If required variable is not found
    """
    value = os.environ.get(key, default)
    
    if required and not value:
        raise ValueError(f"Required environment variable '{key}' is not set")
    
    return value or ""


def _get_env_int(key: str, default: int, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """
    Get integer environment variable with validation.
    
    Args:
        key: Environment variable name
        default: Default value
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Integer value
        
    Raises:
        ValueError: If value is invalid or out of range
    """
    value_str = os.environ.get(key)
    
    if not value_str:
        return default
    
    try:
        value = int(value_str)
    except ValueError:
        raise ValueError(f"Environment variable '{key}' must be an integer, got: {value_str}")
    
    if min_value is not None and value < min_value:
        raise ValueError(f"Environment variable '{key}' must be >= {min_value}, got: {value}")
    
    if max_value is not None and value > max_value:
        raise ValueError(f"Environment variable '{key}' must be <= {max_value}, got: {value}")
    
    return value


def _get_env_bool(key: str, default: bool) -> bool:
    """
    Get boolean environment variable.
    
    Args:
        key: Environment variable name
        default: Default value
        
    Returns:
        Boolean value
    """
    value_str = os.environ.get(key, "").lower()
    
    if not value_str:
        return default
    
    if value_str in ('true', '1', 'yes', 'on'):
        return True
    elif value_str in ('false', '0', 'no', 'off'):
        return False
    else:
        return default


@lru_cache(maxsize=1)
def load_config() -> Config:
    """
    Load configuration from environment variables.
    Cached for performance - configuration is immutable.
    
    Returns:
        Configuration object
        
    Raises:
        ValueError: If configuration is invalid
    """
    try:
        return Config(
            # Google Cloud Platform Configuration
            project_id=_get_env_var('PROJECT_ID', 'unified-intelligence-platform', required=True),
            pubsub_topic=_get_env_var('PUBSUB_TOPIC', 'radar-signals-topic', required=True),
            
            # Performance Configuration (bytes/seconds)
            max_payload_size=_get_env_int('MAX_PAYLOAD_SIZE', 1048576, min_value=1024, max_value=10485760),  # 1KB - 10MB
            validation_timeout=_get_env_int('VALIDATION_TIMEOUT', 5, min_value=1, max_value=30),  # 1-30 seconds
            publish_timeout=_get_env_int('PUBLISH_TIMEOUT', 30, min_value=5, max_value=300),  # 5-300 seconds
            
            # Logging Configuration
            log_level=_get_env_var('LOG_LEVEL', 'INFO').upper(),
            structured_logging=_get_env_bool('STRUCTURED_LOGGING', True),
            
            # Application Configuration
            environment=_get_env_var('ENVIRONMENT', 'development'),
            debug=_get_env_bool('DEBUG', False),
            version=_get_env_var('API_VERSION', '1.0.0'),
            
            # Optional Development Configuration
            google_application_credentials=_get_env_var('GOOGLE_APPLICATION_CREDENTIALS'),
            pubsub_emulator_host=_get_env_var('PUBSUB_EMULATOR_HOST')
        )
        
    except Exception as e:
        raise ValueError(f"Configuration error: {e}")


def validate_config(config: Config) -> None:
    """
    Validate configuration for consistency and requirements.
    
    Args:
        config: Configuration to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Validate log level
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config.log_level not in valid_log_levels:
        raise ValueError(f"Invalid log level '{config.log_level}'. Must be one of: {valid_log_levels}")
    
    # Validate environment
    valid_environments = ['development', 'testing', 'staging', 'production']
    if config.environment.lower() not in valid_environments:
        raise ValueError(f"Invalid environment '{config.environment}'. Must be one of: {valid_environments}")
    
    # Validate project ID format (basic check)
    if not config.project_id or len(config.project_id) < 6:
        raise ValueError("Project ID must be at least 6 characters long")
    
    # Validate Pub/Sub topic name format (basic check)
    if not config.pubsub_topic or len(config.pubsub_topic) < 3:
        raise ValueError("Pub/Sub topic name must be at least 3 characters long")
    
    # Production environment checks
    if config.is_production:
        if config.debug:
            raise ValueError("Debug mode should not be enabled in production")
        
        if config.use_emulator:
            raise ValueError("Pub/Sub emulator should not be used in production")


# Global configuration instance
_global_config: Optional[Config] = None


@lru_cache(maxsize=1)
def get_config() -> Config:
    """
    Get global configuration instance.
    Cached for performance and consistency.
    
    Returns:
        Configuration object
    """
    global _global_config
    
    if _global_config is None:
        _global_config = load_config()
        validate_config(_global_config)
    
    return _global_config


def reload_config() -> Config:
    """
    Reload configuration from environment variables.
    Clears cache and creates new configuration.
    
    Returns:
        New configuration object
    """
    global _global_config
    
    # Clear caches
    load_config.cache_clear()
    get_config.cache_clear()
    
    _global_config = None
    return get_config()


# Convenience functions for common configuration values

def get_project_id() -> str:
    """Get GCP project ID."""
    return get_config().project_id


def get_pubsub_topic() -> str:
    """Get Pub/Sub topic name."""
    return get_config().pubsub_topic


def get_max_payload_size() -> int:
    """Get maximum payload size in bytes."""
    return get_config().max_payload_size


def get_validation_timeout() -> int:
    """Get validation timeout in seconds."""
    return get_config().validation_timeout


def get_publish_timeout() -> int:
    """Get Pub/Sub publish timeout in seconds."""
    return get_config().publish_timeout


def get_log_level() -> str:
    """Get logging level."""
    return get_config().log_level


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return get_config().debug


def is_production() -> bool:
    """Check if running in production."""
    return get_config().is_production


def is_development() -> bool:
    """Check if running in development."""
    return get_config().is_development


# Configuration validation for startup
def validate_startup_config() -> None:
    """
    Validate configuration at startup.
    Raises exception if configuration is invalid.
    
    Raises:
        ValueError: If configuration is invalid
    """
    config = get_config()
    validate_config(config)
    
    # Additional startup validations
    if config.is_production and config.log_level == 'DEBUG':
        raise ValueError("DEBUG log level should not be used in production for performance reasons")


# Environment-specific configuration helpers

def configure_for_testing() -> None:
    """Configure environment for testing."""
    os.environ['ENVIRONMENT'] = 'testing'
    os.environ['DEBUG'] = 'true'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    os.environ['PUBSUB_EMULATOR_HOST'] = 'localhost:8085'
    
    # Clear config cache to pick up changes
    reload_config()


def configure_for_development() -> None:
    """Configure environment for development."""
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['DEBUG'] = 'true'
    os.environ['LOG_LEVEL'] = 'INFO'
    
    # Clear config cache to pick up changes
    reload_config()


def configure_for_production() -> None:
    """Configure environment for production."""
    os.environ['ENVIRONMENT'] = 'production'
    os.environ['DEBUG'] = 'false'
    os.environ['LOG_LEVEL'] = 'INFO'
    
    # Remove emulator configuration if present
    if 'PUBSUB_EMULATOR_HOST' in os.environ:
        del os.environ['PUBSUB_EMULATOR_HOST']
    
    # Clear config cache to pick up changes
    reload_config()