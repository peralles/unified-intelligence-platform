"""
T016 - Health check service

Dependency health monitoring with performance metrics collection.
Service status determination logic for comprehensive observability.
"""
import time
import psutil
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from functools import lru_cache

from src.models.health import (
    HealthResponse, ServiceStatus, DependencyHealth, HealthMetrics, HealthIssue,
    create_dependency_health, create_health_metrics, create_basic_health_response
)
from src.utils.logging import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)


class HealthService:
    """
    Comprehensive health monitoring service.
    Provides dependency status, performance metrics, and issue tracking.
    """
    
    def __init__(self):
        """Initialize health service with configuration and metrics tracking."""
        self.config = get_config()
        self.start_time = time.time()
        
        # Metrics tracking
        self._request_count = 0
        self._error_count = 0
        self._total_latency = 0.0
        self._events_processed_total = 0
        self._events_processed_today = 0
        
        # Cache for expensive operations
        self._last_health_check = None
        self._last_health_check_time = 0
        self._health_check_cache_ttl = 30  # Cache health checks for 30 seconds
        
        logger.debug("Health service initialized")
    
    def get_uptime_seconds(self) -> int:
        """Get service uptime in seconds."""
        return int(time.time() - self.start_time)
    
    def record_request(self, latency_ms: float, success: bool = True) -> None:
        """
        Record request metrics for health monitoring.
        
        Args:
            latency_ms: Request latency in milliseconds
            success: Whether the request was successful
        """
        self._request_count += 1
        self._total_latency += latency_ms
        
        if not success:
            self._error_count += 1
        
        # Update events processed count for successful events
        if success and latency_ms > 0:  # Assuming successful requests are event processing
            self._events_processed_total += 1
            # For simplicity, we'll track daily events as events since startup
            # In production, this would use proper daily counters
            self._events_processed_today += 1
    
    def get_request_rate(self) -> float:
        """Calculate current request rate per second."""
        uptime = self.get_uptime_seconds()
        if uptime == 0:
            return 0.0
        return self._request_count / uptime
    
    def get_average_latency_ms(self) -> float:
        """Calculate average request latency in milliseconds."""
        if self._request_count == 0:
            return 0.0
        return self._total_latency / self._request_count
    
    def get_error_rate_percent(self) -> float:
        """Calculate error rate as percentage."""
        if self._request_count == 0:
            return 0.0
        return (self._error_count / self._request_count) * 100
    
    def check_pubsub_health(self) -> DependencyHealth:
        """
        Check Pub/Sub service health.
        
        Returns:
            DependencyHealth with Pub/Sub status
        """
        start_time = time.time()
        
        try:
            # Import here to avoid circular dependency
            from src.services.publisher import get_publisher
            
            # Perform lightweight health check
            health_result = get_publisher().health_check()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine status based on response time and health result
            if health_result['status'] == 'healthy':
                if response_time_ms > 100:  # >100ms is degraded performance
                    status = ServiceStatus.DEGRADED
                    error_message = f"High latency: {response_time_ms:.2f}ms"
                else:
                    status = ServiceStatus.HEALTHY
                    error_message = None
            else:
                status = ServiceStatus.UNHEALTHY
                error_message = health_result.get('error', 'Unknown Pub/Sub error')
            
            return create_dependency_health(
                status=status,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            logger.warning(
                "Pub/Sub health check failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            
            return create_dependency_health(
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error_message=str(e)
            )
    
    def check_schema_registry_health(self) -> DependencyHealth:
        """
        Check schema registry health (JSON schema file access).
        
        Returns:
            DependencyHealth with schema registry status
        """
        start_time = time.time()
        
        try:
            # Import here to avoid circular dependency
            from src.services.validator import get_validator
            
            # Check if schema is accessible and validator is working
            validator = get_validator()
            schema_stats = validator.get_validation_stats()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Schema registry is healthy if schema is loaded and validator is compiled
            if schema_stats['schema_loaded'] and schema_stats['validator_compiled']:
                if response_time_ms > 50:  # >50ms is degraded for local file access
                    status = ServiceStatus.DEGRADED
                    error_message = f"Slow schema access: {response_time_ms:.2f}ms"
                else:
                    status = ServiceStatus.HEALTHY
                    error_message = None
            else:
                status = ServiceStatus.UNHEALTHY
                error_message = "Schema not loaded or validator not compiled"
            
            return create_dependency_health(
                status=status,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            
            logger.warning(
                "Schema registry health check failed",
                error=str(e),
                response_time_ms=response_time_ms
            )
            
            return create_dependency_health(
                status=ServiceStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                error_message=str(e)
            )
    
    def check_dependencies(self) -> Dict[str, DependencyHealth]:
        """
        Check all external dependencies.
        
        Returns:
            Dictionary mapping dependency names to health status
        """
        dependencies = {}
        
        # Check Pub/Sub
        try:
            dependencies['pubsub'] = self.check_pubsub_health()
        except Exception as e:
            logger.error("Failed to check Pub/Sub health", error=str(e))
            dependencies['pubsub'] = create_dependency_health(
                status=ServiceStatus.UNHEALTHY,
                error_message=f"Health check failed: {str(e)}"
            )
        
        # Check Schema Registry
        try:
            dependencies['schema_registry'] = self.check_schema_registry_health()
        except Exception as e:
            logger.error("Failed to check schema registry health", error=str(e))
            dependencies['schema_registry'] = create_dependency_health(
                status=ServiceStatus.UNHEALTHY,
                error_message=f"Health check failed: {str(e)}"
            )
        
        return dependencies
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system performance metrics.
        
        Returns:
            Dictionary with system metrics
        """
        try:
            process = psutil.Process(os.getpid())
            
            return {
                'memory_usage_mb': process.memory_info().rss / 1024 / 1024,
                'memory_percent': process.memory_percent(),
                'cpu_percent': process.cpu_percent(),
                'num_threads': process.num_threads(),
                'num_file_descriptors': process.num_fds() if hasattr(process, 'num_fds') else None,
                'create_time': process.create_time()
            }
            
        except Exception as e:
            logger.warning("Failed to get system metrics", error=str(e))
            return {
                'error': str(e)
            }
    
    def create_health_metrics(self) -> HealthMetrics:
        """
        Create current health metrics.
        
        Returns:
            HealthMetrics instance with current performance data
        """
        return create_health_metrics(
            uptime_seconds=self.get_uptime_seconds(),
            requests_per_second=self.get_request_rate(),
            average_latency_ms=self.get_average_latency_ms(),
            error_rate_percent=self.get_error_rate_percent(),
            total_events_processed=self._events_processed_total,
            events_processed_today=self._events_processed_today
        )
    
    def detect_issues(self, dependencies: Dict[str, DependencyHealth], metrics: HealthMetrics) -> List[HealthIssue]:
        """
        Detect and create health issues based on current status.
        
        Args:
            dependencies: Current dependency health status
            metrics: Current performance metrics
            
        Returns:
            List of detected issues
        """
        issues = []
        now = datetime.now(timezone.utc)
        
        # Check dependency issues
        for dep_name, dep_health in dependencies.items():
            if dep_health.status == ServiceStatus.UNHEALTHY:
                issues.append(HealthIssue(
                    component=dep_name,
                    message=dep_health.error_message or f"{dep_name} is unhealthy",
                    since=now,
                    severity="critical"
                ))
            elif dep_health.status == ServiceStatus.DEGRADED:
                issues.append(HealthIssue(
                    component=dep_name,
                    message=dep_health.error_message or f"{dep_name} performance degraded",
                    since=now,
                    severity="medium"
                ))
        
        # Check performance issues
        if metrics.error_rate_percent > 5.0:  # >5% error rate
            issues.append(HealthIssue(
                component="api",
                message=f"High error rate: {metrics.error_rate_percent:.1f}%",
                since=now,
                severity="high" if metrics.error_rate_percent > 10.0 else "medium"
            ))
        
        if metrics.average_latency_ms > 200:  # >200ms average latency
            issues.append(HealthIssue(
                component="api",
                message=f"High latency: {metrics.average_latency_ms:.1f}ms",
                since=now,
                severity="medium"
            ))
        
        # Check system resource issues
        system_metrics = self.get_system_metrics()
        if 'memory_percent' in system_metrics and system_metrics['memory_percent'] > 85:
            issues.append(HealthIssue(
                component="system",
                message=f"High memory usage: {system_metrics['memory_percent']:.1f}%",
                since=now,
                severity="high"
            ))
        
        return issues
    
    def calculate_overall_status(self, dependencies: Dict[str, DependencyHealth], issues: List[HealthIssue]) -> ServiceStatus:
        """
        Calculate overall service status based on dependencies and issues.
        
        Args:
            dependencies: Dependency health status
            issues: Detected issues
            
        Returns:
            Overall service status
        """
        # Check for critical issues first
        critical_issues = [issue for issue in issues if issue.severity == "critical"]
        if critical_issues:
            return ServiceStatus.UNHEALTHY
        
        # Check for unhealthy dependencies
        unhealthy_deps = [dep for dep in dependencies.values() if dep.status == ServiceStatus.UNHEALTHY]
        if unhealthy_deps:
            return ServiceStatus.UNHEALTHY
        
        # Check for degraded dependencies or high-severity issues
        degraded_deps = [dep for dep in dependencies.values() if dep.status == ServiceStatus.DEGRADED]
        high_issues = [issue for issue in issues if issue.severity == "high"]
        
        if degraded_deps or high_issues:
            return ServiceStatus.DEGRADED
        
        # Check for medium-severity issues
        medium_issues = [issue for issue in issues if issue.severity == "medium"]
        if medium_issues:
            return ServiceStatus.DEGRADED
        
        return ServiceStatus.HEALTHY
    
    def get_health_status(self, use_cache: bool = True) -> HealthResponse:
        """
        Get comprehensive health status.
        
        Args:
            use_cache: Whether to use cached health check results
            
        Returns:
            HealthResponse with complete status information
        """
        current_time = time.time()
        
        # Check cache if enabled
        if (use_cache and 
            self._last_health_check and 
            (current_time - self._last_health_check_time) < self._health_check_cache_ttl):
            return self._last_health_check
        
        start_time = time.time()
        
        try:
            # Check dependencies
            dependencies = self.check_dependencies()
            
            # Create metrics
            metrics = self.create_health_metrics()
            
            # Detect issues
            issues = self.detect_issues(dependencies, metrics)
            
            # Calculate overall status
            overall_status = self.calculate_overall_status(dependencies, issues)
            
            # Create health response
            health_response = HealthResponse(
                status=overall_status,
                timestamp=datetime.now(timezone.utc),
                version=self.config.version,
                dependencies=dependencies,
                metrics=metrics,
                issues=issues if issues else None
            )
            
            health_check_time_ms = (time.time() - start_time) * 1000
            
            logger.log_health_check(
                status=overall_status.value,
                dependencies={name: dep.status.value for name, dep in dependencies.items()},
                health_check_time_ms=health_check_time_ms,
                issue_count=len(issues)
            )
            
            # Update cache
            if use_cache:
                self._last_health_check = health_response
                self._last_health_check_time = current_time
            
            return health_response
            
        except Exception as e:
            health_check_time_ms = (time.time() - start_time) * 1000
            
            logger.exception(
                "Health check failed",
                health_check_time_ms=health_check_time_ms
            )
            
            # Return basic unhealthy response
            return HealthResponse(
                status=ServiceStatus.UNHEALTHY,
                timestamp=datetime.now(timezone.utc),
                version=self.config.version,
                dependencies={},
                metrics=self.create_health_metrics(),
                issues=[HealthIssue(
                    component="health_service",
                    message=f"Health check failed: {str(e)}",
                    since=datetime.now(timezone.utc),
                    severity="critical"
                )]
            )
    
    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        self._request_count = 0
        self._error_count = 0
        self._total_latency = 0.0
        self._events_processed_total = 0
        self._events_processed_today = 0
        self.start_time = time.time()
        
        # Clear health check cache
        self._last_health_check = None
        self._last_health_check_time = 0
        
        logger.info("Health service metrics reset")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get detailed service statistics."""
        return {
            'uptime_seconds': self.get_uptime_seconds(),
            'request_count': self._request_count,
            'error_count': self._error_count,
            'events_processed_total': self._events_processed_total,
            'events_processed_today': self._events_processed_today,
            'request_rate': self.get_request_rate(),
            'average_latency_ms': self.get_average_latency_ms(),
            'error_rate_percent': self.get_error_rate_percent(),
            'cache_ttl_seconds': self._health_check_cache_ttl,
            'last_health_check_age_seconds': (
                time.time() - self._last_health_check_time 
                if self._last_health_check_time > 0 else None
            ),
            'system_metrics': self.get_system_metrics()
        }


# Global health service instance
_global_health_service: Optional[HealthService] = None


@lru_cache(maxsize=1)
def get_health_service() -> HealthService:
    """
    Get global health service instance.
    
    Returns:
        HealthService instance
    """
    global _global_health_service
    
    if _global_health_service is None:
        _global_health_service = HealthService()
    
    return _global_health_service


def get_health_status(use_cache: bool = True) -> HealthResponse:
    """
    Get health status using global health service.
    
    Args:
        use_cache: Whether to use cached results
        
    Returns:
        HealthResponse with current status
    """
    return get_health_service().get_health_status(use_cache)


def record_request(latency_ms: float, success: bool = True) -> None:
    """
    Record request metrics using global health service.
    
    Args:
        latency_ms: Request latency in milliseconds
        success: Whether the request was successful
    """
    get_health_service().record_request(latency_ms, success)