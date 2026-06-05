"""Pytest configuration and fixtures for session manager tests."""
import json
import pytest
import tempfile
from pathlib import Path

from session_manager import SessionManager


@pytest.fixture
def temp_session_file():
    """Create a temporary session file for testing.
    Yields path to temporary file that is cleaned up after test.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = f.name
    yield Path(temp_path)
    # Cleanup
    temp_file = Path(temp_path)
    if temp_file.exists():
        temp_file.unlink()


@pytest.fixture
def session_mgr(temp_session_file):
    """Create a SessionManager with temporary session file."""
    return SessionManager(session_file=str(temp_session_file))


@pytest.fixture
def dummy_session_state():
    """Return a valid dummy session state object (Playwright storage format)."""
    return {
        "cookies": [
            {
                "name": "li_at",
                "value": "test_token_123",
                "domain": ".linkedin.com",
                "path": "/",
                "expires": 9999999999,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            }
        ],
        "origins": [
            {
                "origin": "https://www.linkedin.com",
                "localStorage": [{"name": "test_key", "value": "test_value"}],
                "sessionStorage": [],
            }
        ],
    }


@pytest.fixture
def dummy_session_file(temp_session_file, dummy_session_state):
    """Create a dummy session.json file with valid structure."""
    with open(temp_session_file, "w") as f:
        json.dump(dummy_session_state, f)
    return temp_session_file
