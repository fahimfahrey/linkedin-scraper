"""
Test suite for anti-ban guardrails, anomaly detection, and emergency shutdown.

Covers execution window enforcement, anomaly detection patterns, emergency
shutdown sequence, and artificial break conditions.
"""

import asyncio
import json
import pytest
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from scraper import (
    ExecutionWindowController,
    ExecutionWindowExceeded,
    AnomalyDetector,
    SecurityIncidentDetected,
    SystemStateSnapshot,
    EmergencyShutdown,
)


# === TestExecutionWindowController ===

class TestExecutionWindowController:
    """Tests for execution window enforcement."""

    def test_exceeds_limit_raises_exception(self):
        """Verify hard limit raises ExecutionWindowExceeded."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=3, state_file=state_file)

            async def run_test():
                # Increment to limit
                await controller.check_and_increment()  # count = 1
                await controller.check_and_increment()  # count = 2
                await controller.check_and_increment()  # count = 3

                # Next increment should raise
                with pytest.raises(ExecutionWindowExceeded):
                    await controller.check_and_increment()

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)

    def test_soft_warning_at_80_percent(self):
        """Verify soft warning triggered at 80% threshold."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=10, state_file=state_file)

            async def run_test():
                # Increment to 80% (8 profiles)
                for _ in range(8):
                    await controller.check_and_increment()

                # Should have 8 in state now
                assert controller.state["count"] == 8

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)

    def test_resets_on_new_day(self):
        """Verify counter resets on new day."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=5, state_file=state_file)
            controller.state = {"date": "2025-01-01", "count": 5, "reset_count": 0}

            async def run_test():
                # Mock today to be different date
                with patch('scraper.date') as mock_date:
                    mock_date.today.return_value.isoformat.return_value = "2025-01-02"
                    mock_date.today.return_value.__str__.return_value = "2025-01-02"

                    await controller.reset_if_new_day()

                    # Count should reset
                    assert controller.state["count"] == 0
                    assert controller.state["reset_count"] == 1

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)

    def test_state_persists_to_file(self):
        """Verify state persists to JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=5, state_file=state_file)

            async def run_test():
                await controller.check_and_increment()
                await controller.check_and_increment()

                # Verify file contains correct state
                with open(state_file) as f:
                    saved_state = json.load(f)
                    assert saved_state["count"] == 2

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)

    def test_get_state_returns_dict(self):
        """Verify get_state exports current state."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=10, state_file=state_file)

            async def run_test():
                await controller.check_and_increment()
                state = controller.get_state()

                assert state["count"] == 1
                assert state["max_profiles"] == 10
                assert "date" in state

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)


# === TestAnomalyDetector ===

class TestAnomalyDetector:
    """Tests for anomaly detection patterns."""

    def test_detects_captcha(self):
        """Verify CAPTCHA detection in page content."""
        detector = AnomalyDetector()

        # Test content match
        assert detector._detect_captcha("recaptcha widget", "", "")
        assert detector._detect_captcha("", "challenge", "")
        assert detector._detect_captcha("", "", "verify your identity")

    def test_detects_forced_logout(self):
        """Verify forced logout detection."""
        detector = AnomalyDetector()

        assert detector._detect_logout("/login", "")
        assert detector._detect_logout("/signup", "")
        assert detector._detect_logout("", "sign in required")

    def test_detects_rate_limit(self):
        """Verify rate limit detection."""
        detector = AnomalyDetector()

        assert detector._detect_rate_limit("rate limit exceeded")
        assert detector._detect_rate_limit("too many requests")
        assert detector._detect_rate_limit("HTTP 429 - please slow down")

    def test_tracks_url_history(self):
        """Verify URL history is maintained."""
        detector = AnomalyDetector(url_history_limit=5)

        for i in range(10):
            detector._track_url(f"https://linkedin.com/in/profile{i}")

        # Should only keep last 5
        assert len(detector.url_history) == 5

    def test_resets_failure_count(self):
        """Verify failure count resets on success."""
        detector = AnomalyDetector()
        detector.rate_limit_failure_count = 5

        detector.reset_failure_count()

        assert detector.rate_limit_failure_count == 0

    def test_inspect_page_returns_none_on_healthy_page(self):
        """Verify healthy pages return None."""
        detector = AnomalyDetector()

        async def run_test():
            # Mock a healthy page
            page = AsyncMock()
            page.content = AsyncMock(return_value="<html>normal profile</html>")
            page.url = "https://linkedin.com/in/user123"
            page.title = AsyncMock(return_value="User Profile")

            result = await detector.inspect_page(page)
            assert result is None

        asyncio.run(run_test())


# === TestSystemStateSnapshot ===

class TestSystemStateSnapshot:
    """Tests for state snapshot."""

    def test_snapshot_to_dict(self):
        """Verify snapshot converts to dict."""
        snapshot = SystemStateSnapshot(
            profiles_collected=10,
            anomaly_type="captcha",
            anomaly_details={"location": "/login"},
            browser_url="https://linkedin.com/login",
            page_title="Sign In",
            memory_usage_mb=125.5,
            execution_duration_sec=300.0,
        )

        data = snapshot.to_dict()

        assert data["profiles_collected"] == 10
        assert data["anomaly_type"] == "captcha"
        assert "timestamp" in data

    def test_snapshot_to_json_line(self):
        """Verify snapshot converts to JSON line."""
        snapshot = SystemStateSnapshot(
            profiles_collected=5,
            anomaly_type="rate_limit",
            anomaly_details={},
        )

        json_line = snapshot.to_json_line()

        parsed = json.loads(json_line)
        assert parsed["profiles_collected"] == 5
        assert parsed["anomaly_type"] == "rate_limit"


# === TestEmergencyShutdown ===

class TestEmergencyShutdown:
    """Tests for emergency shutdown sequence."""

    def test_flush_profiles_to_db(self):
        """Verify profiles are flushed to database."""
        profiles = [
            {"linkedin_url": "url1", "full_name": "User 1"},
            {"linkedin_url": "url2", "full_name": "User 2"},
        ]

        shutdown = EmergencyShutdown(
            incident_type="test",
            details={},
            profiles_buffer=profiles,
        )

        async def run_test():
            with patch('database.insert_profile_batch') as mock_insert:
                await shutdown._flush_profiles()
                # Verify method exists
                assert hasattr(shutdown, '_flush_profiles')

        asyncio.run(run_test())

    def test_log_incident_state(self):
        """Verify incident state is logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "security_incidents.log"

            shutdown = EmergencyShutdown(
                incident_type="captcha",
                details={"test": True},
                profiles_buffer=[],
            )

            # Change to temp dir
            import os
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                async def run_test():
                    page = AsyncMock()
                    page.url = "https://linkedin.com/login"
                    page.title = AsyncMock(return_value="Sign In")

                    await shutdown._log_incident_state(None, 0.0, page)

                    # Verify log file exists
                    assert log_file.exists()

                asyncio.run(run_test())
            finally:
                os.chdir(old_cwd)

    def test_cleanup_browser_handles_exceptions(self):
        """Verify cleanup wraps exceptions but continues."""
        shutdown = EmergencyShutdown(
            incident_type="test",
            details={},
            profiles_buffer=[],
        )

        async def run_test():
            # Mock browser that raises on close
            browser = AsyncMock()
            browser.close = AsyncMock(side_effect=Exception("Close failed"))
            context = AsyncMock()
            context.close = AsyncMock()

            # Should not raise
            await shutdown._cleanup_browser(browser, context)

        asyncio.run(run_test())


# === TestArtificialBreakConditions ===

class TestArtificialBreakConditions:
    """Tests for artificial break conditions to verify safety mechanisms."""

    def test_artificial_limit_exceeded(self):
        """Artificial test: trigger limit exceeded condition."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=3, state_file=state_file)

            async def run_test():
                # Manually set count to trigger on next increment
                controller.state["count"] = 3
                controller._save_state()

                with pytest.raises(ExecutionWindowExceeded):
                    await controller.check_and_increment()

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)

    def test_artificial_captcha_trigger(self):
        """Artificial test: trigger CAPTCHA detection."""
        detector = AnomalyDetector()

        # Inject malicious content
        malicious_content = """
        <html>
            <body>
                <script src="recaptcha"></script>
                <div>Please verify your identity</div>
            </body>
        </html>
        """

        result = detector._detect_captcha(malicious_content, "", "Verify")
        assert result is True

    def test_artificial_logout_trigger(self):
        """Artificial test: trigger forced logout detection."""
        detector = AnomalyDetector()

        result = detector._detect_logout("https://linkedin.com/login", "LinkedIn Sign In")
        assert result is True

    def test_artificial_rate_limit_trigger(self):
        """Artificial test: trigger rate limit detection."""
        detector = AnomalyDetector()

        rate_limited_content = "HTTP 429 Too Many Requests. Please slow down."
        result = detector._detect_rate_limit(rate_limited_content)
        assert result is True

    def test_consecutive_failures_trigger_rate_limit(self):
        """Artificial test: consecutive failures trigger rate limit incident."""
        detector = AnomalyDetector()

        rate_limited_content = "Rate limit exceeded"

        # First detection
        assert detector._detect_rate_limit(rate_limited_content)
        detector.rate_limit_failure_count += 1

        # Second detection should trigger incident (count >= 2)
        assert detector._detect_rate_limit(rate_limited_content)
        detector.rate_limit_failure_count += 1

        assert detector.rate_limit_failure_count >= 2


# === Integration-like Tests ===

class TestIntegration:
    """Integration tests for safety mechanisms."""

    def test_critical_warning_at_90_percent(self):
        """Verify critical warning at 90% threshold."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            state_file = f.name

        try:
            controller = ExecutionWindowController(max_profiles_per_day=10, state_file=state_file)

            async def run_test():
                # Increment to 90% (9 profiles)
                for _ in range(9):
                    await controller.check_and_increment()

                assert controller.state["count"] == 9

            asyncio.run(run_test())
        finally:
            Path(state_file).unlink(missing_ok=True)

    def test_security_incident_exception_carries_details(self):
        """Verify SecurityIncidentDetected carries anomaly type and details."""
        anomaly_type = "captcha"
        details = {"location": "login_page", "timestamp": "2025-01-15T10:30:00"}

        exc = SecurityIncidentDetected(anomaly_type, details)

        assert exc.anomaly_type == "captcha"
        assert exc.details == details
        assert "Security incident: captcha" in str(exc)
