"""
T013 - Health status models

Health check data structures supporting constitutional observability requirements.
Performance metrics tracking models for monitoring and alerting.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ServiceStatus(str, Enum):
    """Service health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

    def __str__(self) -> str:
        return self.value

    @property
    def http_status_code(self) -> int:
        """Get HTTP status code for service status."""
        if self == self.HEALTHY:
            return 200
        else:  # DEGRADED or UNHEALTHY
            return 503


class DependencyHealth(BaseModel):
    """Individual dependency health information."""
    
    model_config = ConfigDict(
        extra='forbid'
    )
    
    status: ServiceStatus = Field(
        description="Health status of the dependency"
    )
    
    response_time_ms: Optional[float] = Field(
        None,
        description="Dependency response time in milliseconds",
        ge=0  # Must be non-negative
    )
    
    last_check: datetime = Field(
        description="Timestamp of last health check"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error description if dependency is unhealthy"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "status": self.status.value,
            "last_check": self.last_check.isoformat().replace('+00:00', 'Z')
        }
        
        if self.response_time_ms is not None:
            result["response_time_ms"] = self.response_time_ms
        
        if self.error_message:
            result["error_message"] = self.error_message
        
        return result

    @property
    def is_healthy(self) -> bool:
        """Check if dependency is healthy."""
        return self.status == ServiceStatus.HEALTHY

    @property
    def is_available(self) -> bool:
        """Check if dependency is available (healthy or degraded)."""
        return self.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]


class HealthMetrics(BaseModel):
    """Operational metrics for monitoring and alerting."""
    
    model_config = ConfigDict(
        extra='forbid'
    )
    
    uptime_seconds: int = Field(
        description="Service uptime in seconds",
        ge=0
    )
    
    requests_per_second: float = Field(
        description="Current request rate",
        ge=0
    )
    
    average_latency_ms: float = Field(
        description="Average response latency in milliseconds",
        ge=0
    )
    
    error_rate_percent: float = Field(
        description="Error rate as percentage",
        ge=0,
        le=100
    )
    
    total_events_processed: int = Field(
        description="Total lifetime events processed",
        ge=0
    )
    
    events_processed_today: int = Field(
        description="Events processed since midnight UTC",
        ge=0
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "uptime_seconds": self.uptime_seconds,
            "requests_per_second": self.requests_per_second,
            "average_latency_ms": self.average_latency_ms,
            "error_rate_percent": self.error_rate_percent,
            "total_events_processed": self.total_events_processed,
            "events_processed_today": self.events_processed_today
        }

    @property
    def uptime_hours(self) -> float:
        """Get uptime in hours."""
        return self.uptime_seconds / 3600.0

    @property
    def uptime_days(self) -> float:
        """Get uptime in days."""
        return self.uptime_seconds / 86400.0

    @property
    def is_performing_well(self) -> bool:
        """Check if service is performing within acceptable parameters."""
        return (
            self.error_rate_percent < 1.0 and  # <1% error rate
            self.average_latency_ms < 100      # <100ms average latency
        )


class HealthIssue(BaseModel):
    """Individual health issue description."""
    
    model_config = ConfigDict(
        extra='forbid'
    )
    
    component: str = Field(
        description="Component name that has the issue",
        examples=["pubsub", "schema_registry"]
    )
    
    message: str = Field(
        description="Description of the issue",
        examples=["High latency detected", "Connection timeout"]
    )
    
    since: datetime = Field(
        description="Timestamp when issue was first detected"
    )
    
    severity: Optional[str] = Field(
        None,
        description="Issue severity level",
        examples=["low", "medium", "high", "critical"]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "component": self.component,
            "message": self.message,
            "since": self.since.isoformat().replace('+00:00', 'Z')
        }
        
        if self.severity:
            result["severity"] = self.severity
        
        return result

    @property
    def duration_seconds(self) -> float:
        """Get duration of the issue in seconds."""
        return (datetime.utcnow() - self.since.replace(tzinfo=None)).total_seconds()

    @property
    def is_recent(self) -> bool:
        """Check if issue occurred within the last 5 minutes."""
        return self.duration_seconds < 300


class HealthResponse(BaseModel):
    """
    Comprehensive health status supporting constitutional observability.
    Enables monitoring, alerting, and operational visibility.
    """
    
    model_config = ConfigDict(
        extra='forbid'
    )
    
    status: ServiceStatus = Field(
        description="Overall service health status"
    )
    
    timestamp: datetime = Field(
        description="Timestamp when health check was performed"
    )
    
    version: str = Field(
        default="1.0.0",
        description="API version for debugging and compatibility"
    )
    
    dependencies: Dict[str, DependencyHealth] = Field(
        default_factory=dict,
        description="Health status of external dependencies"
    )
    
    metrics: HealthMetrics = Field(
        description="Operational metrics and statistics"
    )
    
    issues: Optional[List[HealthIssue]] = Field(
        None,
        description="Current issues affecting service health"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat().replace('+00:00', 'Z'),
            "version": self.version,
            "dependencies": {name: dep.to_dict() for name, dep in self.dependencies.items()},
            "metrics": self.metrics.to_dict()
        }
        
        if self.issues:
            result["issues"] = [issue.to_dict() for issue in self.issues]
        
        return result

    @property
    def http_status_code(self) -> int:
        """Get HTTP status code for health response."""
        return self.status.http_status_code

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status == ServiceStatus.HEALTHY

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        if not self.issues:
            return False
        return any(issue.severity == "critical" for issue in self.issues if issue.severity)

    def add_dependency(self, name: str, dependency: DependencyHealth) -> None:
        """Add a dependency health check."""
        self.dependencies[name] = dependency

    def add_issue(self, component: str, message: str, severity: Optional[str] = None) -> None:
        """Add a health issue."""
        if self.issues is None:
            self.issues = []
        
        issue = HealthIssue(
            component=component,
            message=message,
            since=datetime.utcnow(),
            severity=severity
        )
        self.issues.append(issue)

    def calculate_overall_status(self) -> ServiceStatus:
        """Calculate overall status based on dependencies and issues."""
        if not self.dependencies:
            return ServiceStatus.HEALTHY
        
        # Check for unhealthy dependencies
        unhealthy_deps = [dep for dep in self.dependencies.values() 
                         if dep.status == ServiceStatus.UNHEALTHY]
        
        if unhealthy_deps:
            return ServiceStatus.UNHEALTHY
        
        # Check for degraded dependencies
        degraded_deps = [dep for dep in self.dependencies.values() 
                        if dep.status == ServiceStatus.DEGRADED]
        
        if degraded_deps:
            return ServiceStatus.DEGRADED
        
        # Check for critical issues
        if self.has_critical_issues:
            return ServiceStatus.UNHEALTHY
        
        # Check performance metrics
        if not self.metrics.is_performing_well:
            return ServiceStatus.DEGRADED
        
        return ServiceStatus.HEALTHY

    def update_status(self) -> None:
        """Update overall status based on current dependencies and issues."""
        self.status = self.calculate_overall_status()


# Utility functions for health check creation

def create_dependency_health(
    status: ServiceStatus,
    response_time_ms: Optional[float] = None,
    error_message: Optional[str] = None
) -> DependencyHealth:
    """Create a dependency health check with current timestamp."""
    return DependencyHealth(
        status=status,
        response_time_ms=response_time_ms,
        last_check=datetime.utcnow(),
        error_message=error_message
    )


def create_health_metrics(
    uptime_seconds: int = 0,
    requests_per_second: float = 0.0,
    average_latency_ms: float = 0.0,
    error_rate_percent: float = 0.0,
    total_events_processed: int = 0,
    events_processed_today: int = 0
) -> HealthMetrics:
    """Create health metrics with default values."""
    return HealthMetrics(
        uptime_seconds=uptime_seconds,
        requests_per_second=requests_per_second,
        average_latency_ms=average_latency_ms,
        error_rate_percent=error_rate_percent,
        total_events_processed=total_events_processed,
        events_processed_today=events_processed_today
    )


def create_basic_health_response(
    status: ServiceStatus = ServiceStatus.HEALTHY,
    version: str = "1.0.0"
) -> HealthResponse:
    """Create a basic health response with minimal metrics."""
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=version,
        dependencies={},
        metrics=create_health_metrics()
    )