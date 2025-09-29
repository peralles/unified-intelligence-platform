"""
T010 - Performance test concurrent request handling

Load testing framework for concurrent requests
This test MUST FAIL initially before implementation.
"""
import pytest
import json
import uuid
import time
import asyncio
import statistics
from datetime import datetime
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, as_completed


@pytest.fixture
def performance_event():
    """Event for performance testing."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_timestamp": datetime.utcnow().isoformat() + "Z",
        "event_source": "performance-test-service",
        "event_type": "test.performance.concurrent_load",
        "event_version": "1.0.0",
        "payload": {
            "test_scenario": "concurrent_performance_testing",
            "load_level": "high",
            "expected_latency": "sub_100ms"
        }
    }


class TestConcurrentPerformance:
    """Performance tests for concurrent request handling."""

    def _create_mock_request(self, event_data, trace_id=None):
        """Helper to create mock request for performance tests."""
        mock_request = Mock()
        mock_request.method = "POST"
        headers = {"Content-Type": "application/json"}
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        mock_request.headers = headers
        mock_request.get_json.return_value = event_data
        return mock_request

    def _setup_mock_pubsub(self, success_rate=1.0):
        """Helper to setup mock Pub/Sub with configurable success rate."""
        def publish_side_effect(*args, **kwargs):
            if success_rate < 1.0:
                import random
                if random.random() > success_rate:
                    from google.api_core import exceptions
                    raise exceptions.ServiceUnavailable("Simulated failure")
            
            future_mock = Mock()
            future_mock.result.return_value = f"msg-{uuid.uuid4().hex[:8]}"
            return future_mock
        
        patcher = patch('google.cloud.pubsub_v1.PublisherClient')
        mock_client_class = patcher.start()
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.topic_path.return_value = "projects/test/topics/radar-signals"
        mock_client.publish.side_effect = publish_side_effect
        
        return patcher

    @pytest.mark.performance
    def test_single_request_latency_target(self, performance_event):
        """Test single request meets <100ms latency target."""
        # Will FAIL until main function is implemented
        from src.main import main
        
        with self._setup_mock_pubsub():
            mock_request = self._create_mock_request(performance_event)
            
            # Measure single request latency
            start_time = time.time()
            response = main(mock_request)
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            
            # Assert response is correct
            assert response[1] == 202
            
            # Assert latency target (generous for test environment)
            assert latency_ms < 200, f"Latency {latency_ms:.2f}ms exceeds 200ms target"
            
            print(f"Single request latency: {latency_ms:.2f}ms")

    @pytest.mark.performance
    def test_concurrent_request_handling(self, performance_event):
        """Test concurrent request handling without interference."""
        from src.main import main
        
        with self._setup_mock_pubsub():
            concurrent_requests = 10
            
            def process_request(request_id):
                """Process a single request and return timing info."""
                event_copy = performance_event.copy()
                event_copy["event_id"] = str(uuid.uuid4())
                event_copy["payload"]["request_id"] = request_id
                
                mock_request = self._create_mock_request(event_copy, f"trace-{request_id}")
                
                start_time = time.time()
                response = main(mock_request)
                end_time = time.time()
                
                return {
                    "request_id": request_id,
                    "latency_ms": (end_time - start_time) * 1000,
                    "status_code": response[1],
                    "response": response
                }
            
            # Execute concurrent requests
            with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                futures = [executor.submit(process_request, i) for i in range(concurrent_requests)]
                results = [future.result() for future in as_completed(futures)]
            
            # Analyze results
            latencies = [r["latency_ms"] for r in results]
            status_codes = [r["status_code"] for r in results]
            
            # All requests should succeed
            assert all(code == 202 for code in status_codes), f"Failed status codes: {status_codes}"
            
            # Performance analysis
            avg_latency = statistics.mean(latencies)
            p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
            max_latency = max(latencies)
            
            print(f"Concurrent performance - Requests: {concurrent_requests}")
            print(f"  Average latency: {avg_latency:.2f}ms")
            print(f"  95th percentile: {p95_latency:.2f}ms")
            print(f"  Maximum latency: {max_latency:.2f}ms")
            
            # Performance assertions (generous for test environment)
            assert avg_latency < 300, f"Average latency {avg_latency:.2f}ms too high"
            assert p95_latency < 500, f"P95 latency {p95_latency:.2f}ms too high"

    @pytest.mark.performance
    def test_sustained_throughput_performance(self, performance_event):
        """Test sustained throughput over time."""
        from src.main import main
        
        with self._setup_mock_pubsub():
            duration_seconds = 5
            request_interval = 0.1  # 10 requests per second
            
            results = []
            start_test_time = time.time()
            
            while (time.time() - start_test_time) < duration_seconds:
                event_copy = performance_event.copy()
                event_copy["event_id"] = str(uuid.uuid4())
                
                mock_request = self._create_mock_request(event_copy)
                
                request_start = time.time()
                response = main(mock_request)
                request_end = time.time()
                
                results.append({
                    "timestamp": request_start,
                    "latency_ms": (request_end - request_start) * 1000,
                    "status_code": response[1]
                })
                
                # Wait for next request
                time.sleep(request_interval)
            
            # Analyze sustained performance
            total_requests = len(results)
            successful_requests = sum(1 for r in results if r["status_code"] == 202)
            success_rate = successful_requests / total_requests
            
            latencies = [r["latency_ms"] for r in results if r["status_code"] == 202]
            throughput = total_requests / duration_seconds
            
            print(f"Sustained performance over {duration_seconds}s:")
            print(f"  Total requests: {total_requests}")
            print(f"  Success rate: {success_rate:.2%}")
            print(f"  Throughput: {throughput:.1f} req/s")
            if latencies:
                print(f"  Average latency: {statistics.mean(latencies):.2f}ms")
            
            # Performance assertions
            assert success_rate >= 0.95, f"Success rate {success_rate:.2%} too low"
            assert throughput >= 8.0, f"Throughput {throughput:.1f} req/s too low"

    @pytest.mark.performance
    def test_memory_usage_under_load(self, performance_event):
        """Test memory usage remains stable under concurrent load."""
        from src.main import main
        import psutil
        import os
        
        with self._setup_mock_pubsub():
            process = psutil.Process(os.getpid())
            
            # Baseline memory usage
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Generate load
            concurrent_requests = 20
            
            def memory_intensive_request(request_id):
                event_copy = performance_event.copy()
                event_copy["event_id"] = str(uuid.uuid4())
                event_copy["payload"]["request_id"] = request_id
                
                mock_request = self._create_mock_request(event_copy)
                return main(mock_request)
            
            # Execute concurrent requests
            with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                futures = [executor.submit(memory_intensive_request, i) 
                          for i in range(concurrent_requests)]
                responses = [future.result() for future in as_completed(futures)]
            
            # Check memory usage after load
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = peak_memory - baseline_memory
            
            print(f"Memory usage - Baseline: {baseline_memory:.1f}MB, Peak: {peak_memory:.1f}MB")
            print(f"Memory increase: {memory_increase:.1f}MB")
            
            # All requests should succeed
            status_codes = [r[1] for r in responses]
            assert all(code == 202 for code in status_codes)
            
            # Memory should not increase excessively (generous limit)
            assert memory_increase < 100, f"Memory increase {memory_increase:.1f}MB too high"

    @pytest.mark.performance
    def test_performance_with_validation_errors(self, performance_event):
        """Test performance when handling validation errors."""
        from src.main import main
        
        # Mix of valid and invalid events
        invalid_event = {
            "event_id": "not-a-uuid",
            "event_timestamp": "invalid-timestamp",
            "event_source": "",
            "event_type": "invalid-format",
            "event_version": "not.semantic",
            "payload": {}
        }
        
        with self._setup_mock_pubsub():
            request_count = 20
            invalid_ratio = 0.5  # 50% invalid requests
            
            results = []
            
            for i in range(request_count):
                # Use invalid event for half the requests
                event = invalid_event if i < (request_count * invalid_ratio) else performance_event
                event_copy = event.copy()
                if "event_id" not in event_copy or event_copy["event_id"] != "not-a-uuid":
                    event_copy["event_id"] = str(uuid.uuid4())
                
                mock_request = self._create_mock_request(event_copy)
                
                start_time = time.time()
                response = main(mock_request)
                end_time = time.time()
                
                results.append({
                    "request_type": "invalid" if i < (request_count * invalid_ratio) else "valid",
                    "latency_ms": (end_time - start_time) * 1000,
                    "status_code": response[1]
                })
            
            # Analyze mixed workload performance
            valid_results = [r for r in results if r["request_type"] == "valid"]
            invalid_results = [r for r in results if r["request_type"] == "invalid"]
            
            valid_latencies = [r["latency_ms"] for r in valid_results]
            invalid_latencies = [r["latency_ms"] for r in invalid_results]
            
            print(f"Mixed workload performance:")
            print(f"  Valid requests - Avg: {statistics.mean(valid_latencies):.2f}ms")
            print(f"  Invalid requests - Avg: {statistics.mean(invalid_latencies):.2f}ms")
            
            # Valid requests should succeed and be fast
            valid_status_codes = [r["status_code"] for r in valid_results]
            assert all(code == 202 for code in valid_status_codes)
            assert statistics.mean(valid_latencies) < 300
            
            # Invalid requests should fail fast
            invalid_status_codes = [r["status_code"] for r in invalid_results]
            assert all(code == 400 for code in invalid_status_codes)
            assert statistics.mean(invalid_latencies) < 200  # Should be faster (no Pub/Sub)

    @pytest.mark.performance
    def test_performance_degradation_with_pubsub_failures(self, performance_event):
        """Test performance characteristics when Pub/Sub has intermittent failures."""
        from src.main import main
        
        # 80% success rate for Pub/Sub
        with self._setup_mock_pubsub(success_rate=0.8):
            request_count = 25
            results = []
            
            for i in range(request_count):
                event_copy = performance_event.copy()
                event_copy["event_id"] = str(uuid.uuid4())
                
                mock_request = self._create_mock_request(event_copy)
                
                start_time = time.time()
                response = main(mock_request)
                end_time = time.time()
                
                results.append({
                    "latency_ms": (end_time - start_time) * 1000,
                    "status_code": response[1]
                })
            
            # Analyze performance under failure conditions
            success_count = sum(1 for r in results if r["status_code"] == 202)
            failure_count = sum(1 for r in results if r["status_code"] == 503)
            success_rate = success_count / request_count
            
            successful_latencies = [r["latency_ms"] for r in results if r["status_code"] == 202]
            failed_latencies = [r["latency_ms"] for r in results if r["status_code"] == 503]
            
            print(f"Performance under Pub/Sub failures:")
            print(f"  Success rate: {success_rate:.2%}")
            print(f"  Successful requests avg latency: {statistics.mean(successful_latencies):.2f}ms")
            print(f"  Failed requests avg latency: {statistics.mean(failed_latencies):.2f}ms")
            
            # Should handle failures gracefully
            assert success_rate >= 0.7  # Should match Pub/Sub success rate approximately
            assert failure_count > 0  # Should have some failures
            
            # Failed requests should still be reasonably fast (fail-fast principle)
            if failed_latencies:
                assert statistics.mean(failed_latencies) < 200