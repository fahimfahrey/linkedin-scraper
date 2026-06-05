import os
import subprocess
import pytest
from src.browser_config import get_chromium_executable_path, validate_chromium_executable


def test_chromium_executable_exists():
    """Verify Chromium executable is found at expected path."""
    executable_path = get_chromium_executable_path()
    assert executable_path is not None, "Chromium executable not found"
    assert os.path.exists(executable_path), f"Chromium path does not exist: {executable_path}"
    assert os.path.isfile(executable_path), f"Chromium path is not a file: {executable_path}"


def test_chromium_executable_is_executable():
    """Verify Chromium executable has execute permission."""
    executable_path = get_chromium_executable_path()
    assert os.access(executable_path, os.X_OK), f"Chromium not executable: {executable_path}"


def test_chromium_returns_version():
    """Verify Chromium responds to --version flag."""
    executable_path = get_chromium_executable_path()
    result = subprocess.run(
        [executable_path, "--version"],
        capture_output=True,
        text=True,
        timeout=10
    )
    assert result.returncode == 0, f"Chromium --version failed: {result.stderr}"
    assert "Chromium" in result.stdout or "Chrome" in result.stdout, \
        f"Version string unexpected: {result.stdout}"


def test_validate_chromium_executable_success():
    """Verify validation function returns True for valid executable."""
    result = validate_chromium_executable()
    assert result is True, "Chromium validation failed"


def test_validate_chromium_executable_with_missing_path():
    """Verify validation fails gracefully when executable missing."""
    invalid_path = "/nonexistent/path/chromium"
    result = validate_chromium_executable(invalid_path)
    assert result is False, "Should return False for missing executable"


def test_env_file_skip_download_set():
    """Verify PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD prevents downloads."""
    # This will be set by pytest fixture in Task 3
    # Just verify the constant is correct
    assert os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD") == "1"


def test_env_file_chromium_path_set():
    """Verify explicit path environment variable is set."""
    expected_path = "/usr/bin/chromium-browser"
    actual_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    assert actual_path == expected_path, f"Expected {expected_path}, got {actual_path}"


@pytest.mark.asyncio
async def test_playwright_browser_initializes_with_manual_chromium():
    """Verify Playwright can launch and use manual Chromium."""
    from playwright.async_api import async_playwright
    from src.browser_config import get_browser_launch_args

    launch_args = get_browser_launch_args()

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context()
        page = await context.new_page()

        # Simple smoke test: navigate to about:blank
        await page.goto("about:blank")
        title = await page.title()

        await page.close()
        await context.close()
        await browser.close()

        assert title == "", "about:blank should have empty title"
