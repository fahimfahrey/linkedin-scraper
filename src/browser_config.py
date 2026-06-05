import os
import subprocess
from pathlib import Path
from typing import Optional


DEFAULT_CHROMIUM_PATH = "/usr/bin/chromium-browser"


def get_chromium_executable_path(custom_path: Optional[str] = None) -> Optional[str]:
    """
    Locate Chromium executable for Playwright.

    Args:
        custom_path: Custom path to check first (overrides default)

    Returns:
        Full path to Chromium executable, or None if not found
    """
    paths_to_check = []

    if custom_path:
        paths_to_check.append(custom_path)

    paths_to_check.append(DEFAULT_CHROMIUM_PATH)
    paths_to_check.extend([
        "/usr/bin/chromium",
        "/snap/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ])

    for path in paths_to_check:
        if os.path.exists(path) and os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def validate_chromium_executable(executable_path: Optional[str] = None) -> bool:
    """
    Validate Chromium executable works by running --version.

    Args:
        executable_path: Path to validate. If None, use default discovery.

    Returns:
        True if executable found and responds to --version, False otherwise
    """
    path = executable_path or get_chromium_executable_path()

    if not path:
        return False

    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def get_browser_launch_args() -> dict:
    """
    Return Playwright launch args configured for manual Chromium.

    Returns:
        Dict with 'executable_path' key pointing to Chromium

    Raises:
        RuntimeError if Chromium executable not found or not valid
    """
    executable_path = get_chromium_executable_path()

    if not executable_path:
        raise RuntimeError(
            f"Chromium executable not found. Checked: {DEFAULT_CHROMIUM_PATH} and common alternatives. "
            "Install Chromium with: sudo apt-get install chromium-browser"
        )

    if not validate_chromium_executable(executable_path):
        raise RuntimeError(
            f"Chromium executable at {executable_path} failed validation. "
            "Verify it is executable: chmod +x {executable_path}"
        )

    return {
        "executable_path": executable_path,
    }
