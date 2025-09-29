"""
T006 - Contract test GET /healthz endpoint against OpenAPI specification

This test MUST FAIL initially as it tests against the API contract
before any implementation exists.
"""
import pytest
import json
from unittest.mock import Mock, patch


class TestHealthAPIContract:
    """Contract tests for GET /healthz endpoint per OpenAPI specification."""

    @pytest.mark.contract
    def test_get_healthz_healthy_returns_200(self):
        """Test healthy service returns 200 OK with proper format."""
        # This test will FAIL until health endpoint is implemented
        from src.main import main  # This import will fail initially
        from unittest.mock import patch, Mock
        
        # Mock Pub/Sub health check to return healthy status
        with patch('src.services.publisher.get_publisher') as mock_get_publisher:
            mock_publisher = Mock()
            mock_publisher.health_check.return_value = {
                'status': 'healthy',
                'response_time_ms': 5.0,
                'topic_path': 'projects/test/topics/radar-signals',
                'project_id': 'test-project',
                'topic_name': 'radar-signals-topic'
            }
            mock_get_publisher.return_value = mock_publisher
            
            mock_request = Mock()
            mock_request.method = "GET"
            mock_request.path = "/healthz"
            mock_request.headers = {}
            
            response = main(mock_request)
            
            # Contract assertions per OpenAPI spec
            assert response[1] == 200  # HTTP 200 OK
            
            response_data = json.loads(response[0])
            
            # Required fields per contract
            assert response_data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "timestamp" in response_data
            assert "version" in response_data
            assert "dependencies" in response_data
            assert "metrics" in response_data
            
            # Dependencies structure
            dependencies = response_data["dependencies"]
            assert "pubsub" in dependencies
            assert "schema_registry" in dependencies
            
            for dep_name, dep_info in dependencies.items():
                assert dep_info["status"] in ["healthy", "degraded", "unhealthy"]
                assert "last_check" in dep_info
                if dep_info["status"] != "unhealthy":
                    assert "response_time_ms" in dep_info
            
            # Metrics structure
            metrics = response_data["metrics"]
            required_metrics = [
                "uptime_seconds",
                "requests_per_second", 
                "average_latency_ms",
                "error_rate_percent",
                "total_events_processed",
                "events_processed_today"
            ]
            
            for metric in required_metrics:
                assert metric in metrics
                assert isinstance(metrics[metric], (int, float))

    @pytest.mark.contract
    def test_get_healthz_degraded_returns_200_with_issues(self):
        """Test degraded service returns 200 with issues field."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.path = "/healthz"
        
        # Mock degraded Pub/Sub
        with patch('src.services.health.HealthService.check_dependencies') as mock_deps:
            mock_deps.return_value = {
                "pubsub": {
                    "status": "degraded",
                    "response_time_ms": 150.0,
                    "last_check": "2025-09-28T14:30:00.000Z",
                    "error_message": "High latency detected"
                },
                "schema_registry": {
                    "status": "healthy",
                    "response_time_ms": 1.2,
                    "last_check": "2025-09-28T14:30:00.000Z"
                }
            }
            
            response = main(mock_request)
            
            assert response[1] == 200
            
            response_data = json.loads(response[0])
            assert response_data["status"] == "degraded"
            assert "issues" in response_data
            assert isinstance(response_data["issues"], list)
            
            # Should have at least one issue
            assert len(response_data["issues"]) > 0
            
            issue = response_data["issues"][0]
            assert "component" in issue
            assert "message" in issue
            assert "since" in issue

    @pytest.mark.contract
    def test_get_healthz_unhealthy_returns_503(self):
        """Test unhealthy service returns 503 Service Unavailable."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.path = "/healthz"
        
        # Mock unhealthy Pub/Sub
        with patch('src.services.health.HealthService.check_dependencies') as mock_deps:
            mock_deps.return_value = {
                "pubsub": {
                    "status": "unhealthy",
                    "response_time_ms": None,
                    "last_check": "2025-09-28T14:25:00.000Z",
                    "error_message": "Connection timeout after 30s"
                },
                "schema_registry": {
                    "status": "healthy", 
                    "response_time_ms": 1.2,
                    "last_check": "2025-09-28T14:30:00.000Z"
                }
            }
            
            response = main(mock_request)
            
            assert response[1] == 503  # HTTP 503 Service Unavailable
            
            response_data = json.loads(response[0])
            assert response_data["status"] == "unhealthy"
            assert "issues" in response_data

    @pytest.mark.contract
    def test_get_healthz_response_performance(self):
        """Test health check responds quickly (<10ms target)."""
        from src.main import main
        import time
        
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.path = "/healthz"
        
        start_time = time.time()
        response = main(mock_request)
        end_time = time.time()
        
        # Health check should be fast
        response_time_ms = (end_time - start_time) * 1000
        assert response_time_ms < 100  # Generous for test environment
        
        # Should still return valid response
        assert response[1] in [200, 503]

    @pytest.mark.contract
    def test_get_healthz_version_info_present(self):
        """Test version information is included in health response."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.path = "/healthz"
        
        response = main(mock_request)
        response_data = json.loads(response[0])
        
        assert "version" in response_data
        assert response_data["version"] == "1.0.0"

    @pytest.mark.contract 
    def test_get_healthz_timestamp_format(self):
        """Test timestamp is in correct ISO 8601 format."""
        from src.main import main
        from datetime import datetime
        
        mock_request = Mock()
        mock_request.method = "GET"
        mock_request.path = "/healthz"
        
        response = main(mock_request)
        response_data = json.loads(response[0])
        
        # Verify timestamp format
        timestamp_str = response_data["timestamp"]
        
        # Should be parseable as ISO 8601
        parsed_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        assert parsed_timestamp is not None
        
        # Should be recent (within last minute)
        now = datetime.utcnow()
        time_diff = abs((now - parsed_timestamp.replace(tzinfo=None)).total_seconds())
        assert time_diff < 60  # Within last minute

    @pytest.mark.contract
    def test_get_healthz_content_type_json(self):
        """Test health response has correct Content-Type header."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "GET" 
        mock_request.path = "/healthz"
        
        response = main(mock_request)
        
        # Response should include headers
        if len(response) > 2:
            headers = response[2]
            assert headers["Content-Type"] == "application/json"