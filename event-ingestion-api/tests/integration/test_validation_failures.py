"""
T008 - Integration test schema validation failures

Test various validation scenarios from quickstart.md
This test MUST FAIL initially before implementation.
"""
import pytest
import json
import uuid
from datetime import datetime
from unittest.mock import Mock


class TestValidationFailuresIntegration:
    """Integration tests for schema validation error scenarios."""

    @pytest.mark.integration
    def test_missing_required_fields_validation(self):
        """Test validation failures for missing required fields."""
        # Will FAIL until main function and validation are implemented
        from src.main import main
        
        test_cases = [
            # Missing event_id
            {
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "test.validation.missing_id",
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # Missing event_timestamp 
            {
                "event_id": str(uuid.uuid4()),
                "event_source": "test-service",
                "event_type": "test.validation.missing_timestamp", 
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # Missing event_source
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_type": "test.validation.missing_source",
                "event_version": "1.0.0", 
                "payload": {"test": "data"}
            },
            # Missing event_type
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # Missing event_version
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z", 
                "event_source": "test-service",
                "event_type": "test.validation.missing_version",
                "payload": {"test": "data"}
            },
            # Missing payload
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "test.validation.missing_payload",
                "event_version": "1.0.0"
            }
        ]
        
        for invalid_event in test_cases:
            mock_request = Mock()
            mock_request.method = "POST"
            mock_request.headers = {"Content-Type": "application/json"}
            mock_request.get_json.return_value = invalid_event
            
            response = main(mock_request)
            
            # Should return validation error
            assert response[1] == 400
            response_data = json.loads(response[0])
            assert response_data["error"] == "VALIDATION_FAILED"
            assert "details" in response_data
            assert len(response_data["details"]) > 0
            assert response_data["retryable"] is False

    @pytest.mark.integration
    def test_invalid_data_format_validation(self):
        """Test validation failures for invalid data formats."""
        from src.main import main
        
        test_cases = [
            # Invalid UUID format
            {
                "event_id": "not-a-valid-uuid",
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "test.validation.invalid_uuid",
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # Invalid timestamp format
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "invalid-timestamp-format",
                "event_source": "test-service", 
                "event_type": "test.validation.invalid_timestamp",
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # Invalid event_source format (empty string)
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "",
                "event_type": "test.validation.invalid_source", 
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # Invalid event_type format (missing dots)
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "invalid-format-no-dots",
                "event_version": "1.0.0", 
                "payload": {"test": "data"}
            },
            # Invalid event_version format (not semantic version)
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "test.validation.invalid_version",
                "event_version": "not.semantic.version.format",
                "payload": {"test": "data"}
            },
            # Empty payload object
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service", 
                "event_type": "test.validation.empty_payload",
                "event_version": "1.0.0",
                "payload": {}
            }
        ]
        
        for invalid_event in test_cases:
            mock_request = Mock()
            mock_request.method = "POST"
            mock_request.headers = {"Content-Type": "application/json"}
            mock_request.get_json.return_value = invalid_event
            
            response = main(mock_request)
            
            assert response[1] == 400
            response_data = json.loads(response[0])
            assert response_data["error"] == "VALIDATION_FAILED"
            assert "details" in response_data
            
            # Should have specific field validation details
            details = response_data["details"]
            assert len(details) > 0
            
            # Each detail should have field and message
            for detail in details:
                assert "field" in detail
                assert "message" in detail
                assert isinstance(detail["field"], str)
                assert isinstance(detail["message"], str)

    @pytest.mark.integration
    def test_boundary_value_validation_failures(self):
        """Test validation failures at boundary values."""
        from src.main import main
        
        test_cases = [
            # event_source too long (>100 characters)
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "a" * 101,  # 101 characters
                "event_type": "test.validation.source_too_long",
                "event_version": "1.0.0",
                "payload": {"test": "data"}
            },
            # event_type too long (>200 characters)
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "test." + "a" * 190 + ".toolong",  # >200 chars
                "event_version": "1.0.0", 
                "payload": {"test": "data"}
            },
            # payload with too many properties (>50)
            {
                "event_id": str(uuid.uuid4()),
                "event_timestamp": "2025-09-28T14:30:00.000Z",
                "event_source": "test-service",
                "event_type": "test.validation.payload_too_many_props",
                "event_version": "1.0.0",
                "payload": {f"prop_{i}": f"value_{i}" for i in range(51)}  # 51 props
            }
        ]
        
        for invalid_event in test_cases:
            mock_request = Mock()
            mock_request.method = "POST"
            mock_request.headers = {"Content-Type": "application/json"}
            mock_request.get_json.return_value = invalid_event
            
            response = main(mock_request)
            
            assert response[1] == 400
            response_data = json.loads(response[0])
            assert response_data["error"] == "VALIDATION_FAILED"

    @pytest.mark.integration
    def test_detailed_validation_error_messages(self):
        """Test that validation errors provide detailed, actionable messages."""
        from src.main import main
        
        # Multiple validation errors in single request
        invalid_event = {
            "event_id": "not-a-uuid",
            "event_timestamp": "invalid-timestamp",
            "event_source": "",
            "event_type": "invalid-format",
            "event_version": "not.semantic.version",
            "payload": {}
        }
        
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.get_json.return_value = invalid_event
        
        response = main(mock_request)
        
        assert response[1] == 400
        response_data = json.loads(response[0])
        
        # Should have multiple validation errors
        details = response_data["details"]
        assert len(details) >= 4  # At least 4 validation errors
        
        # Check that errors are specific and actionable
        field_names = [detail["field"] for detail in details]
        expected_fields = ["event_id", "event_timestamp", "event_source", "event_type", "event_version", "payload"]
        
        # Should have errors for most/all invalid fields
        invalid_field_count = sum(1 for field in expected_fields if any(field in fn for fn in field_names))
        assert invalid_field_count >= 4

    @pytest.mark.integration
    def test_json_syntax_error_handling(self):
        """Test handling of invalid JSON syntax."""
        from src.main import main
        
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.get_json.side_effect = ValueError("Invalid JSON syntax")
        
        response = main(mock_request)
        
        assert response[1] == 400
        response_data = json.loads(response[0])
        assert response_data["error"] == "VALIDATION_FAILED"
        assert "JSON" in response_data["message"]
        assert response_data["retryable"] is False

    @pytest.mark.integration
    def test_content_type_validation(self):
        """Test Content-Type header validation."""
        from src.main import main
        
        valid_event = {
            "event_id": str(uuid.uuid4()),
            "event_timestamp": "2025-09-28T14:30:00.000Z",
            "event_source": "test-service",
            "event_type": "test.validation.content_type",
            "event_version": "1.0.0",
            "payload": {"test": "data"}
        }
        
        # Test missing Content-Type
        mock_request = Mock()
        mock_request.method = "POST"
        mock_request.headers = {}
        mock_request.get_json.return_value = valid_event
        
        response = main(mock_request)
        
        assert response[1] == 400
        response_data = json.loads(response[0])
        assert "Content-Type" in response_data["message"]
        
        # Test invalid Content-Type
        mock_request.headers = {"Content-Type": "text/plain"}
        response = main(mock_request)
        
        assert response[1] == 400
        response_data = json.loads(response[0])
        assert "Content-Type" in response_data["message"]