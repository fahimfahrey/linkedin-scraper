"""Centralized Chromium/Linux OS environment mapping."""

import os
import logging

logger = logging.getLogger(__name__)


def get_chromium_environment() -> dict:
    """
    Return Linux Chromium environment mapping for headless execution.
    Ensures Chromium runs stably with proper display, library, and temp paths.
    """
    env = {
        "DISPLAY": os.environ.get("DISPLAY", ":99"),  # Xvfb for headless
        "PATH": os.environ.get("PATH", ""),
        "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH", ""),
        "HOME": os.environ.get("HOME", "/home/user"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }

    # Validate critical keys
    if not env.get("DISPLAY"):
        logger.warning(
            "DISPLAY not set and defaulted to :99 (Xvfb). "
            "Ensure Xvfb is running or DISPLAY is properly configured."
        )

    if not env.get("HOME"):
        logger.warning("HOME not set; defaulting to /home/user.")

    return env


def validate_chromium_environment(env: dict) -> bool:
    """
    Validate environment dict has required keys and non-None values.
    Returns True if valid, False otherwise.
    """
    required_keys = ["DISPLAY", "PATH", "HOME", "TMPDIR"]
    for key in required_keys:
        if not env.get(key):
            logger.error(f"Environment validation failed: {key} is missing or empty.")
            return False
    return True
