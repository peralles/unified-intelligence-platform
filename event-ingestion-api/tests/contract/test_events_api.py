"""
T005 - Contract test POST / endpoint against OpenAPI specification

This test MUST FAIL initially as it tests against the API contract
before any implementation exists.
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime
import uuid


@pytest.fixture
def valid_event_payload():
    """Valid radar signal event payload for testing."""
    # Create timestamp with exactly 3 decimal places for milliseconds
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    return {
        "eventId": str(uuid.uuid4()),
        "eventTimestamp": timestamp,
        "eventSource": "test-service",
        "eventType": "test.contract.validation",
        "eventVersion": "1.0.0",
        "payload": {
            "test_case": "contract_validation",
            "description": "Testing API contract compliance"
        }
    }


@pytest.fixture
def invalid_event_missing_field():
    """Invalid event missing required field for error testing."""
    # Create timestamp with exactly 3 decimal places for milliseconds
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    return {
        "eventId": str(uuid.uuid4()),
        "eventTimestamp": timestamp,
        "eventSource": "test-service",
        "eventVersion": "1.0.0",
        "payload": {"test": "data"}
        # Missing eventType - should trigger validation error
    }


class TestEventsAPIContract:
    """Contract tests for POST / endpoint per OpenAPI specification."""

    @pytest.mark.contract
    def test_post_events_successful_ingestion_returns_202(self, valid_event_payload):
        """Test successful event ingestion returns 202 Accepted per contract."""
        # This test will FAIL until main function is implemented
        from src.main import main  # This import will fail initially
        from unittest.mock import patch, AsyncMock
        
        # Mock Pub/Sub publishing to avoid needing real credentials
        # We need to mock the function where it's imported in main.py
        with patch('src.main.publish_event', new_callable=AsyncMock) as mock_publish:
            # Configure mock to return a message ID
            mock_publish.return_value = "test-message-id-12345"
            
            # Mock Cloud Functions request
            mock_request = Mock()
            mock_request.method = "POST"
            mock_request.path = "/"
            mock_request.headers = {"Content-Type": "application/json"}
            mock_request.get_json.return_value = valid_event_payload
            mock_request.get_data.return_value = json.dumps(valid_event_payload).encode('utf-8')
            
            # Call the function
            response = main(mock_request)
            
            # Contract assertions per OpenAPI spec
            assert response[1] == 202  # HTTP 202 Accepted
            
            response_data = json.loads(response[0])
            assert response_data["status"] == "accepted"
            assert response_data["event_id"] == valid_event_payload["eventId"]  # Note: response uses snake_case
            assert "trace_id" in response_data
            assert "timestamp" in response_data
            assert "message_id" in response_data
            assert response_data["message_id"] == "test-message-id-12345"
            
            # Verify publisher was called
            mock_publish.assert_called_once()

    @pytest.mark.contract 
    def test_post_events_validation_failure_returns_400(self, invalid_event_missing_field):
        """Test validation failure returns 400 Bad Request per contract."""
        # This test will FAIL until validation is implemented
        from src.main import main
        from unittest.mock import patch, AsyncMock
        
        # Mock Pub/Sub (should not be called due to validation failure)
        with patch('src.main.publish_event', new_callable=AsyncMock) as mock_publish:
            mock_request = Mock()
            mock_request.method = "POST"
            mock_request.path = "/"
            mock_request.headers = {"Content-Type": "application/json"}
            mock_request.get_json.return_value = invalid_event_missing_field
            mock_request.get_data.return_value = json.dumps(invalid_event_missing_field).encode('utf-8')
            
            response = main(mock_request)
            
            # Contract assertions per OpenAPI spec
            assert response[1] == 400  # HTTP 400 Bad Request
            
            response_data = json.loads(response[0])
            assert response_data["error"] == "VALIDATION_FAILED"
            assert "message" in response_data
            assert "details" in response_data
            assert isinstance(response_data["details"], list)
            assert len(response_data["details"]) > 0
            assert "trace_id" in response_data
            assert "timestamp" in response_data
            assert response_data["retryable"] is False
            
            # Publisher should not have been called due to validation failure
            mock_publish.assert_not_called()

    @pytest.mark.contract
    def test_post_events_oversized_payload_returns_413(self):
        """Test oversized payload returns 413 Payload Too Large."""
        from src.main import main
        
        # Create payload >1MB
        large_payload = {
            "event_id": str(uuid.uuid4()),
            "event_timestamp": datetime.utcnow().isoformat() + "Z",
            "event_source": "test-service", 
            "event_type": "test.contract.large_payload",
            "event_version": "1.0.0",
            "payload": {"large_data": "x" * 1048577}  # >1MB
        }
        
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.get_json.return_value = large_payload
        
        response = main(mock_request)
        
        assert response[1] == 413  # HTTP 413 Payload Too Large
        
        response_data = json.loads(response[0])
        assert response_data["error"] == "PAYLOAD_TOO_LARGE"
        assert "1MB" in response_data["message"]
        assert response_data["retryable"] is False

    @pytest.mark.contract
    def test_post_events_pubsub_failure_returns_503(self, valid_event_payload):
        """Test Pub/Sub service unavailable returns 503."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "POST" 
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.get_json.return_value = valid_event_payload
        
        # Mock Pub/Sub failure
        with patch('src.services.publisher.PublisherService.publish_event') as mock_publish:
            mock_publish.side_effect = Exception("Pub/Sub unavailable")
            
            response = main(mock_request)
            
            assert response[1] == 503  # HTTP 503 Service Unavailable
            
            response_data = json.loads(response[0])
            assert response_data["error"] == "SERVICE_UNAVAILABLE"
            assert response_data["retryable"] is True
            assert "retry_after" in response_data

    @pytest.mark.contract
    def test_post_events_invalid_json_returns_400(self):
        """Test invalid JSON syntax returns 400."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.get_json.side_effect = ValueError("Invalid JSON")
        
        response = main(mock_request)
        
        assert response[1] == 400
        
        response_data = json.loads(response[0])
        assert response_data["error"] == "VALIDATION_FAILED"
        assert "JSON" in response_data["message"]

    @pytest.mark.contract
    def test_post_events_invalid_content_type_returns_400(self, valid_event_payload):
        """Test invalid Content-Type header returns 400."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {"Content-Type": "text/plain"}
        mock_request.get_json.return_value = valid_event_payload
        
        response = main(mock_request)
        
        assert response[1] == 400
        
        response_data = json.loads(response[0])
        assert "Content-Type" in response_data["message"]

    @pytest.mark.contract
    def test_post_events_response_headers_present(self, valid_event_payload):
        """Test response includes required headers per OpenAPI spec."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.get_json.return_value = valid_event_payload
        
        response = main(mock_request)
        
        # Response should be tuple: (body, status_code, headers)
        if len(response) > 2:
            headers = response[2]
            assert "X-Trace-ID" in headers
            assert "X-Message-ID" in headers
            assert headers["Content-Type"] == "application/json"