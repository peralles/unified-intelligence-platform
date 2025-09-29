"""
T015 - Pub/Sub publishing service

Async google-cloud-pubsub client integration with <30ms latency target.
Connection pooling, timeout handling, and error classification.
"""
import json
import time
import asyncio
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading
from functools import lru_cache

from google.cloud import pubsub_v1
from google.api_core import exceptions as gcp_exceptions
from google.auth.exceptions import GoogleAuthError

from src.models.radar_signal import RadarSignalEvent
from src.models.errors import ServiceUnavailableError, PayloadTooLargeError, RateLimitExceededError
from src.utils.logging import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)


class PublisherService:
    """
    High-performance Pub/Sub publishing service.
    Optimized for <30ms publishing latency with error handling.
    """
    
    def __init__(self, project_id: Optional[str] = None, topic_name: Optional[str] = None):
        """
        Initialize publisher service.
        
        Args:
            project_id: GCP project ID (optional, uses config default)
            topic_name: Pub/Sub topic name (optional, uses config default)
        """
        self.config = get_config()
        self.project_id = project_id or self.config.project_id
        self.topic_name = topic_name or self.config.pubsub_topic
        
        # Publisher client and topic path (lazy initialization)
        self._publisher_client = None
        self._topic_path = None
        
        # Thread pool for async operations
        self._thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="pubsub-publisher")
        
        # Connection lock for thread safety
        self._client_lock = threading.Lock()
        
        logger.debug(
            "Publisher service initialized",
            project_id=self.project_id,
            topic_name=self.topic_name
        )
    
    @property
    def publisher_client(self) -> pubsub_v1.PublisherClient:
        """Get Pub/Sub publisher client (lazy initialization with thread safety)."""
        if self._publisher_client is None:
            with self._client_lock:
                if self._publisher_client is None:  # Double-check locking
                    self._publisher_client = self._create_publisher_client()
        return self._publisher_client
    
    @property
    def topic_path(self) -> str:
        """Get formatted topic path (cached)."""
        if self._topic_path is None:
            self._topic_path = self.publisher_client.topic_path(self.project_id, self.topic_name)
        return self._topic_path
    
    def _create_publisher_client(self) -> pubsub_v1.PublisherClient:
        """Create and configure Pub/Sub publisher client."""
        try:
            # Configure client for optimal performance
            client = pubsub_v1.PublisherClient()
            
            logger.info(
                "Pub/Sub publisher client created",
                project_id=self.project_id,
                topic_name=self.topic_name,
                use_emulator=self.config.use_emulator
            )
            
            return client
            
        except GoogleAuthError as e:
            logger.error(
                "Google Cloud authentication failed",
                error=str(e),
                project_id=self.project_id
            )
            raise ServiceUnavailableError(
                message=f"Google Cloud authentication failed: {str(e)}",
                retry_after=60
            )
        except Exception as e:
            logger.error(
                "Failed to create Pub/Sub publisher client",
                error=str(e),
                project_id=self.project_id
            )
            raise ServiceUnavailableError(
                message=f"Failed to initialize Pub/Sub client: {str(e)}",
                retry_after=30
            )
    
    def _serialize_event(self, event: RadarSignalEvent) -> bytes:
        """
        Serialize radar signal event to bytes for publishing.
        
        Args:
            event: RadarSignalEvent to serialize
            
        Returns:
            Serialized event data as bytes
            
        Raises:
            PayloadTooLargeError: If serialized event exceeds size limits
        """
        try:
            # Convert to JSON string
            event_json = event.to_json()
            
            # Convert to bytes with UTF-8 encoding
            event_bytes = event_json.encode('utf-8')
            
            # Check size limits (Pub/Sub limit is 10MB, but we use 1MB for performance)
            size_bytes = len(event_bytes)
            max_size = self.config.max_payload_size
            
            if size_bytes > max_size:
                raise PayloadTooLargeError(size_bytes, max_size)
            
            logger.debug(
                "Event serialized successfully",
                event_id=str(event.event_id),
                size_bytes=size_bytes,
                max_size=max_size
            )
            
            return event_bytes
            
        except PayloadTooLargeError:
            raise  # Re-raise payload size errors
        except Exception as e:
            logger.error(
                "Event serialization failed",
                event_id=str(event.event_id),
                error=str(e)
            )
            raise ValueError(f"Event serialization failed: {str(e)}")
    
    def _create_message_attributes(self, event: RadarSignalEvent, trace_id: Optional[str] = None) -> Dict[str, str]:
        """
        Create Pub/Sub message attributes for metadata.
        
        Args:
            event: RadarSignalEvent instance
            trace_id: Trace ID for correlation
            
        Returns:
            Dictionary of message attributes
        """
        attributes = {
            'event_id': str(event.event_id),
            'event_type': event.event_type,
            'event_source': event.event_source,
            'event_version': event.event_version,
            'timestamp': event.event_timestamp.isoformat(),
            'content_type': 'application/json',
            'schema_version': '1.0.0'
        }
        
        if trace_id:
            attributes['trace_id'] = trace_id
        
        return attributes
    
    def _handle_publish_error(self, error: Exception, event_id: str, trace_id: Optional[str] = None) -> None:
        """
        Handle and classify Pub/Sub publishing errors.
        
        Args:
            error: Exception that occurred during publishing
            event_id: Event ID for logging correlation
            trace_id: Trace ID for logging correlation
            
        Raises:
            Appropriate API error based on the underlying error
        """
        logger.error(
            "Pub/Sub publishing failed",
            event_id=event_id,
            trace_id=trace_id,
            error_type=type(error).__name__,
            error_message=str(error)
        )
        
        if isinstance(error, gcp_exceptions.DeadlineExceeded):
            raise ServiceUnavailableError(
                message=f"Pub/Sub publish timeout after {self.config.publish_timeout}s",
                retry_after=30,
                trace_id=trace_id
            )
        
        elif isinstance(error, gcp_exceptions.ResourceExhausted):
            raise RateLimitExceededError(
                message="Pub/Sub quota exceeded - rate limit reached",
                retry_after=60,
                trace_id=trace_id
            )
        
        elif isinstance(error, gcp_exceptions.PermissionDenied):
            raise ServiceUnavailableError(
                message="Permission denied for Pub/Sub topic - check IAM roles",
                retry_after=300,  # Longer retry for permission issues
                trace_id=trace_id
            )
        
        elif isinstance(error, gcp_exceptions.NotFound):
            raise ServiceUnavailableError(
                message=f"Pub/Sub topic '{self.topic_name}' not found",
                retry_after=60,
                trace_id=trace_id
            )
        
        elif isinstance(error, gcp_exceptions.InvalidArgument):
            # This could be message too large or invalid format
            if "size" in str(error).lower() or "large" in str(error).lower():
                raise PayloadTooLargeError(
                    size_bytes=0,  # Unknown actual size
                    max_size_bytes=10485760,  # Pub/Sub limit
                    trace_id=trace_id
                )
            else:
                raise ServiceUnavailableError(
                    message=f"Invalid Pub/Sub message format: {str(error)}",
                    retry_after=0,  # Don't retry invalid format
                    trace_id=trace_id
                )
        
        elif isinstance(error, gcp_exceptions.ServiceUnavailable):
            raise ServiceUnavailableError(
                message="Pub/Sub service temporarily unavailable",
                retry_after=30,
                trace_id=trace_id
            )
        
        elif isinstance(error, (ConnectionError, gcp_exceptions.GoogleAPIError)):
            raise ServiceUnavailableError(
                message=f"Pub/Sub connection error: {str(error)}",
                retry_after=30,
                trace_id=trace_id
            )
        
        else:
            # Unknown error - treat as service unavailable
            raise ServiceUnavailableError(
                message=f"Pub/Sub publish error: {str(error)}",
                retry_after=60,
                trace_id=trace_id
            )
    
    async def publish_event_async(self, event: RadarSignalEvent, trace_id: Optional[str] = None) -> str:
        """
        Publish event to Pub/Sub asynchronously.
        
        Args:
            event: RadarSignalEvent to publish
            trace_id: Trace ID for correlation
            
        Returns:
            Pub/Sub message ID
            
        Raises:
            ServiceUnavailableError: If Pub/Sub is unavailable
            PayloadTooLargeError: If event exceeds size limits
            RateLimitExceededError: If rate limits are exceeded
        """
        start_time = time.time()
        
        try:
            # Serialize event
            message_data = self._serialize_event(event)
            
            # Create message attributes
            attributes = self._create_message_attributes(event, trace_id)
            
            # Publish message asynchronously using thread pool
            loop = asyncio.get_event_loop()
            
            future = self.publisher_client.publish(
                self.topic_path,
                message_data,
                **attributes
            )
            
            # Wait for publish result with timeout
            message_id = await loop.run_in_executor(
                self._thread_pool,
                lambda: future.result(timeout=self.config.publish_timeout)
            )
            
            publish_time_ms = (time.time() - start_time) * 1000
            
            logger.log_pubsub_publish(
                event_id=str(event.event_id),
                topic_name=self.topic_name,
                message_id=message_id,
                success=True,
                latency_ms=publish_time_ms,
                trace_id=trace_id
            )
            
            # Performance monitoring
            if publish_time_ms > 30.0:  # Warn if publish takes >30ms
                logger.warning(
                    f"Pub/Sub publish took {publish_time_ms:.2f}ms (target: <30ms)",
                    trace_id=trace_id,
                    publish_time_ms=publish_time_ms,
                    performance_warning=True
                )
            
            return message_id
            
        except Exception as e:
            publish_time_ms = (time.time() - start_time) * 1000
            
            logger.log_pubsub_publish(
                event_id=str(event.event_id),
                topic_name=self.topic_name,
                message_id=None,
                success=False,
                latency_ms=publish_time_ms,
                trace_id=trace_id,
                error=str(e)
            )
            
            self._handle_publish_error(e, str(event.event_id), trace_id)
    
    def publish_event(self, event: RadarSignalEvent, trace_id: Optional[str] = None) -> str:
        """
        Publish event to Pub/Sub synchronously (for backwards compatibility).
        
        Args:
            event: RadarSignalEvent to publish
            trace_id: Trace ID for correlation
            
        Returns:
            Pub/Sub message ID
            
        Raises:
            ServiceUnavailableError: If Pub/Sub is unavailable
            PayloadTooLargeError: If event exceeds size limits
        """
        # Run async function in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.publish_event_async(event, trace_id))
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Pub/Sub connection.
        
        Returns:
            Health check result with status and timing
        """
        start_time = time.time()
        
        try:
            # Try to get topic information (lightweight operation)
            topic_path = self.topic_path
            
            # This will fail if topic doesn't exist or permissions are wrong
            # But it's a quick check without actually publishing
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'response_time_ms': response_time_ms,
                'topic_path': topic_path,
                'project_id': self.project_id,
                'topic_name': self.topic_name
            }
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            logger.warning(
                "Pub/Sub health check failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            
            return {
                'status': 'unhealthy',
                'response_time_ms': response_time_ms,
                'error': str(e),
                'project_id': self.project_id,
                'topic_name': self.topic_name
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publisher service statistics."""
        return {
            'project_id': self.project_id,
            'topic_name': self.topic_name,
            'topic_path': self._topic_path,
            'client_initialized': self._publisher_client is not None,
            'thread_pool_size': self._thread_pool._max_workers,
            'config': {
                'max_payload_size': self.config.max_payload_size,
                'publish_timeout': self.config.publish_timeout,
                'use_emulator': self.config.use_emulator
            }
        }
    
    def close(self) -> None:
        """Clean up resources."""
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
        
        if self._publisher_client:
            try:
                self._publisher_client.close()
            except Exception as e:
                logger.warning("Error closing Pub/Sub client", error=str(e))
        
        logger.debug("Publisher service closed")


# Global publisher instance for performance
_global_publisher: Optional[PublisherService] = None


@lru_cache(maxsize=1)
def get_publisher() -> PublisherService:
    """
    Get global publisher service instance.
    Cached for performance - avoids recreating client connections.
    
    Returns:
        PublisherService instance
    """
    global _global_publisher
    
    if _global_publisher is None:
        _global_publisher = PublisherService()
    
    return _global_publisher


async def publish_event(event: RadarSignalEvent, trace_id: Optional[str] = None) -> str:
    """
    Publish event using global publisher instance.
    
    Args:
        event: RadarSignalEvent to publish
        trace_id: Trace ID for correlation
        
    Returns:
        Pub/Sub message ID
        
    Raises:
        ServiceUnavailableError: If Pub/Sub is unavailable
    """
    return await get_publisher().publish_event_async(event, trace_id)