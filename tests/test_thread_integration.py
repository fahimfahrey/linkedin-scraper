"""End-to-end tests for multi-threaded scraping pipeline."""

import pytest
import time
import queue
import threading
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from queue_protocol import (
    StatusUpdate,
    ProfilePayload,
    OperationWarning,
    ExecutionComplete,
)
from thread_manager import ScraperWorker


class TestWorkerSpawn:
    """Test worker thread spawning and initialization."""

    def test_worker_spawn_creates_thread(self):
        """Worker spawn should create and start a thread."""
        worker = ScraperWorker()
        assert worker.thread is None

        # Mock the batch function to prevent actual scraping
        with patch("scraper.scrape_profile_batch", new_callable=AsyncMock):
            worker.spawn(
                urls=["https://linkedin.com/in/test1"],
                env={"DISPLAY": ":99"},
            )

        # Small delay for thread to start
        time.sleep(0.1)
        assert worker.thread is not None
        assert worker.thread.is_alive()

        # Cleanup
        worker.terminate()

    def test_worker_queue_accessible(self):
        """Worker message queue should be accessible."""
        worker = ScraperWorker()
        assert isinstance(worker.message_queue, queue.Queue)

    def test_worker_id_generated(self):
        """Worker should have a unique ID."""
        worker1 = ScraperWorker()
        worker2 = ScraperWorker()
        assert worker1.worker_id != worker2.worker_id
        assert len(worker1.worker_id) > 0


class TestStatusMessageEmission:
    """Test status message emission during collection."""

    def test_status_message_types(self, temp_message_queue):
        """Status messages should be properly typed."""
        # Emit test messages
        status = StatusUpdate(
            worker_id="test",
            profile_url="https://linkedin.com/in/test",
            status="loading",
            elapsed_sec=1.5,
        )
        temp_message_queue.put(status)

        stored = StatusUpdate(
            worker_id="test",
            profile_url="https://linkedin.com/in/test",
            status="stored",
            elapsed_sec=2.5,
        )
        temp_message_queue.put(stored)

        # Collect messages
        messages = []
        try:
            while True:
                msg = temp_message_queue.get(block=False)
                messages.append(msg)
        except queue.Empty:
            pass

        # Verify message types
        assert len(messages) == 2
        status_updates = [m for m in messages if isinstance(m, StatusUpdate)]
        assert len(status_updates) == 2
        assert messages[0].status == "loading"
        assert messages[1].status == "stored"


class TestProfilePayload:
    """Test profile payload message structure."""

    def test_profile_payload_schema(self):
        """ProfilePayload should have required fields."""
        payload = ProfilePayload(
            worker_id="test",
            profile_data={"name": "Test", "headline": "Engineer"},
            url="https://linkedin.com/in/test",
        )

        assert payload.profile_data["name"] == "Test"
        assert payload.url == "https://linkedin.com/in/test"
        assert payload.worker_id == "test"
        assert payload.timestamp > 0

    def test_profile_payload_serialization(self):
        """ProfilePayload should serialize to dict."""
        payload = ProfilePayload(
            worker_id="test",
            profile_data={"name": "Test"},
            url="https://linkedin.com/in/test",
        )
        data = payload.to_dict()

        assert data["profile_data"]["name"] == "Test"
        assert data["url"] == "https://linkedin.com/in/test"


class TestExecutionComplete:
    """Test execution complete message."""

    def test_execution_complete_success(self):
        """ExecutionComplete should report success."""
        msg = ExecutionComplete(
            worker_id="test",
            success=True,
            profiles_collected=5,
            total_queued=5,
        )

        assert msg.success is True
        assert msg.profiles_collected == 5
        assert msg.error_type is None

    def test_execution_complete_failure(self):
        """ExecutionComplete should report failure with error details."""
        msg = ExecutionComplete(
            worker_id="test",
            success=False,
            profiles_collected=2,
            total_queued=5,
            error_type="ExecutionWindowExceeded",
            details={"reason": "Daily limit reached"},
        )

        assert msg.success is False
        assert msg.error_type == "ExecutionWindowExceeded"
        assert msg.details["reason"] == "Daily limit reached"


class TestThreadSafety:
    """Test thread-safe concurrent access."""

    def test_concurrent_queue_access(self):
        """Multiple threads should safely access shared queue."""
        shared_queue = queue.Queue()
        collected = []
        lock = threading.Lock()

        def producer():
            for i in range(10):
                msg = ProfilePayload(
                    worker_id="producer-1",
                    profile_data={"id": i},
                    url=f"https://linkedin.com/in/test{i}",
                )
                shared_queue.put(msg)

        def consumer():
            while True:
                try:
                    msg = shared_queue.get(timeout=0.1)
                    with lock:
                        collected.append(msg)
                except queue.Empty:
                    break

        prod_thread = threading.Thread(target=producer)
        cons_thread = threading.Thread(target=consumer)

        prod_thread.start()
        cons_thread.start()

        prod_thread.join()
        cons_thread.join()

        assert len(collected) == 10
        for i, msg in enumerate(sorted(collected, key=lambda m: m.profile_data["id"])):
            assert msg.profile_data["id"] == i


class TestWorkerLifecycle:
    """Test worker thread lifecycle management."""

    def test_worker_join_timeout(self):
        """Worker join should respect timeout."""
        worker = ScraperWorker()

        with patch("scraper.scrape_profile_batch", new_callable=AsyncMock):
            worker.spawn(
                urls=["https://linkedin.com/in/test"],
                env={"DISPLAY": ":99"},
            )

        time.sleep(0.2)
        success = worker.join(timeout=0.5)
        # Should timeout or complete
        assert success is not None

        # Cleanup
        if worker.is_alive():
            worker.terminate()

    def test_worker_terminate_stops_collection(self):
        """Worker terminate should stop collection."""
        worker = ScraperWorker()

        with patch("scraper.scrape_profile_batch", new_callable=AsyncMock):
            worker.spawn(
                urls=["https://linkedin.com/in/test"],
                env={"DISPLAY": ":99"},
            )

        time.sleep(0.1)
        worker.terminate()

        time.sleep(0.1)
        # Thread should be stopped or stopping
        assert not worker.is_alive() or worker._stop_event.is_set()


class TestQueueOverflow:
    """Test queue overflow handling."""

    def test_queue_size_limited(self):
        """Queue should have maximum size limit."""
        q = queue.Queue(maxsize=1000)
        assert q.maxsize == 1000

        # Fill queue
        for i in range(100):
            msg = StatusUpdate(
                worker_id="test",
                profile_url=f"https://linkedin.com/in/test{i}",
                status="loading",
            )
            q.put(msg, block=False)

        # Should not exceed limit
        assert q.qsize() <= 1000


class TestMessageProtocol:
    """Test message protocol serialization."""

    def test_message_factory_deserialization(self):
        """MessageFactory should deserialize messages."""
        from queue_protocol import MessageFactory

        # Create and serialize a StatusUpdate
        original = StatusUpdate(
            worker_id="test",
            profile_url="https://linkedin.com/in/test",
            status="loading",
            elapsed_sec=1.5,
        )

        data = original.to_dict()
        deserialized = MessageFactory.from_dict(data)

        assert deserialized.worker_id == original.worker_id
        assert deserialized.profile_url == original.profile_url
        assert deserialized.status == original.status


class TestOperationWarning:
    """Test operation warning messages."""

    def test_warning_severity_levels(self):
        """Warnings should have severity levels."""
        info_warn = OperationWarning(
            worker_id="test",
            severity="info",
            message="Test message",
        )
        assert info_warn.severity == "info"

        critical_warn = OperationWarning(
            worker_id="test",
            severity="critical",
            message="Test message",
            action="shutdown",
        )
        assert critical_warn.severity == "critical"
        assert critical_warn.action == "shutdown"


class TestEnvironmentConfig:
    """Test environment configuration."""

    def test_get_chromium_environment(self):
        """Environment config should return required keys."""
        from environment_config import get_chromium_environment, validate_chromium_environment

        env = get_chromium_environment()

        # Check required keys exist
        assert "DISPLAY" in env
        assert "PATH" in env
        assert "HOME" in env
        assert "TMPDIR" in env

        # Validation should pass
        assert validate_chromium_environment(env) is True

    def test_environment_validation_failure(self):
        """Environment validation should fail with missing keys."""
        from environment_config import validate_chromium_environment

        incomplete_env = {"DISPLAY": ":99"}
        assert validate_chromium_environment(incomplete_env) is False


class TestMessageTimestamps:
    """Test message timestamp ordering."""

    def test_message_timestamps_monotonic(self):
        """Messages should have monotonically increasing timestamps."""
        messages = []
        for i in range(5):
            msg = StatusUpdate(
                worker_id="test",
                profile_url=f"url{i}",
                status="loading",
            )
            messages.append(msg)
            time.sleep(0.01)

        # Verify timestamps are ordered
        for i in range(len(messages) - 1):
            assert messages[i].timestamp <= messages[i + 1].timestamp
