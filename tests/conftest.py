"""Pytest configuration and fixtures for session manager tests."""
import json
import os
import pytest
import tempfile
import queue
import threading
from pathlib import Path
from unittest.mock import MagicMock

from session_manager import SessionManager
from src.browser_config import get_browser_launch_args

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path=None):
        """Fallback if python-dotenv not installed."""
        if path and os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()


def pytest_configure(config):
    """Load environment variables from .env.test before tests run."""
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env.test")
    if os.path.exists(env_file):
        load_dotenv(env_file)

    # Fallback if env var not set
    if not os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"):
        os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"


@pytest.fixture(scope="session")
def playwright_browser_launch_args():
    """
    Return Playwright launch arguments with manual Chromium path.
    Fixture overrides default Playwright fixture behavior.
    """
    return get_browser_launch_args()


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


@pytest.fixture
def temp_message_queue():
    """Create a temporary message queue for testing."""
    return queue.Queue(maxsize=1000)


@pytest.fixture
def mock_scraper_worker():
    """Create a mock ScraperWorker for testing."""
    worker = MagicMock()
    worker.is_alive.return_value = False
    worker.message_queue = queue.Queue()
    worker.worker_id = "test-worker"
    return worker


@pytest.fixture
def app_session_state():
    """Pre-initialized session state dict for testing."""
    return {
        "scraper_worker": None,
        "collection_active": False,
        "collected_profiles": [],
        "status_log": [],
        "thread_lock": threading.Lock(),
        "current_warning": None,
        "last_message_check": 0.0,
    }
