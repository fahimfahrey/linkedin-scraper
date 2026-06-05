# Playwright Chromium Configuration for Ubuntu 26.04 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure Playwright to use the manually installed Chromium browser at `/usr/bin/chromium-browser` on Ubuntu 26.04 where system package dependencies are unavailable or broken.

**Architecture:** Create a browser executable resolver that validates and registers the manual Chromium installation with Playwright, bypass native browser installation via `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` environment variable, and configure pytest fixtures to use the discovered executable path. This avoids fighting unavailable system packages and leverages the existing manual installation.

**Tech Stack:** Playwright (1.60.0), pytest, Python 3.14, environment variables

---

## Files To Create or Modify

| File | Purpose | Type |
|------|---------|------|
| `src/browser_config.py` | Locate and validate Chromium executable, export paths | Create |
| `conftest.py` | Configure pytest session with manual Chromium path | Modify |
| `.env.test` | Test environment variables (executable path, skip downloads) | Create |
| `tests/test_browser_setup.py` | Verify Chromium detection and Playwright initialization | Create |

---

## Architecture Decisions

1. **Skip Native Browser Download:** Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` to prevent Playwright trying to download browsers (which would fail).

2. **Executable Path Registration:** Create a browser config module that:
   - Validates `/usr/bin/chromium-browser` exists and is executable
   - Returns full path and metadata for use in Playwright launch options
   - Raises clear errors if browser not found (helpful debugging)

3. **Fixture-Based Injection:** Modify `conftest.py` to load browser path at session start, inject into all fixtures that create Playwright sessions.

4. **No Architecture Changes to Tests:** Tests remain unchanged—they call existing fixtures, which now use manual Chromium.

---

## Implementation Steps

### Task 1: Create Browser Configuration Module

**Files:**
- Create: `src/browser_config.py`
- Test: `tests/test_browser_setup.py`

- [ ] **Step 1: Write failing test for browser detection**

Create `tests/test_browser_setup.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/test_browser_setup.py -v
```

Expected output:
```
FAILED tests/test_browser_setup.py::test_chromium_executable_exists - ModuleNotFoundError: No module named 'src.browser_config'
```

- [ ] **Step 3: Write minimal implementation**

Create `src/browser_config.py`:

```python
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
        Dict with 'executablePath' key pointing to Chromium
    
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
        "executablePath": executable_path,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/test_browser_setup.py -v
```

Expected output:
```
tests/test_browser_setup.py::test_chromium_executable_exists PASSED
tests/test_browser_setup.py::test_chromium_executable_is_executable PASSED
tests/test_browser_setup.py::test_chromium_returns_version PASSED
tests/test_browser_setup.py::test_validate_chromium_executable_success PASSED
tests/test_browser_setup.py::test_validate_chromium_executable_with_missing_path PASSED

===== 5 passed in 0.45s =====
```

- [ ] **Step 5: Commit**

```bash
cd /home/fahim/linkedin-scraper
git add src/browser_config.py tests/test_browser_setup.py
git commit -m "feat: add browser executable discovery and validation module"
```

---

### Task 2: Configure Environment Variables

**Files:**
- Create: `.env.test`
- Modify: `conftest.py`

- [ ] **Step 1: Create test environment file**

Create `.env.test`:

```
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium-browser
HEADLESS=true
```

Explanation:
- `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`: Prevent Playwright attempting to download missing browsers
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`: Explicit path to manual Chromium (fallback if discovery fails)
- `HEADLESS=true`: Run browsers headless in CI/test environments

- [ ] **Step 2: Write test to verify environment loading**

Add to `tests/test_browser_setup.py`:

```python
def test_env_file_skip_download_set():
    """Verify PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD prevents downloads."""
    import os
    # This will be set by pytest fixture in Task 3
    # Just verify the constant is correct
    assert os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD") == "1"


def test_env_file_chromium_path_set():
    """Verify explicit path environment variable is set."""
    import os
    expected_path = "/usr/bin/chromium-browser"
    actual_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    assert actual_path == expected_path, f"Expected {expected_path}, got {actual_path}"
```

- [ ] **Step 3: Load environment in conftest.py**

Read current `conftest.py` to see existing fixtures, then modify:

```python
import os
import pytest
from dotenv import load_dotenv
from src.browser_config import get_browser_launch_args


# Load .env.test at session start
def pytest_configure(config):
    """Load environment variables from .env.test before tests run."""
    env_file = os.path.join(os.path.dirname(__file__), ".env.test")
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
```

- [ ] **Step 4: Run test to verify environment loads**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/test_browser_setup.py::test_env_file_skip_download_set -v
python -m pytest tests/test_browser_setup.py::test_env_file_chromium_path_set -v
```

Expected output:
```
tests/test_browser_setup.py::test_env_file_skip_download_set PASSED
tests/test_browser_setup.py::test_env_file_chromium_path_set PASSED
```

- [ ] **Step 5: Commit**

```bash
cd /home/fahim/linkedin-scraper
git add .env.test conftest.py
git commit -m "feat: configure environment variables for manual Chromium"
```

---

### Task 3: Integrate Browser Config with Existing Fixtures

**Files:**
- Modify: `conftest.py`
- Modify: `src/conftest.py` (if exists—check structure)

- [ ] **Step 1: Review existing Playwright fixtures in conftest.py**

```bash
cd /home/fahim/linkedin-scraper
grep -n "def.*browser\|def.*context\|def.*page" conftest.py
```

Expected: Lines showing any async browser/context/page fixtures. If none exist, you only need the session fixture from Task 2.

- [ ] **Step 2: Inject browser launch args into Playwright fixture**

Modify conftest.py to inject launch args into any existing browser fixture:

```python
import asyncio
from playwright.async_api import async_playwright
from src.browser_config import get_browser_launch_args


@pytest.fixture(scope="session")
async def browser_context_args():
    """
    Return context args for Playwright fixtures.
    Playwright-pytest plugin uses this to configure browser context.
    """
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
async def browser(playwright_browser_launch_args):
    """
    Override or provide browser fixture with manual Chromium path.
    
    This fixture launches a browser using the manually installed Chromium.
    """
    launch_args = playwright_browser_launch_args
    async with async_playwright() as p:
        chromium_browser = await p.chromium.launch(**launch_args)
        yield chromium_browser
        await chromium_browser.close()


@pytest.fixture(scope="function")
async def page(browser):
    """
    Provide page fixture using the manually-launched browser.
    """
    context = await browser.new_context()
    page_instance = await context.new_page()
    yield page_instance
    await page_instance.close()
    await context.close()
```

- [ ] **Step 3: Run existing tests to verify fixtures work**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/ -v -k "not slow" --tb=short 2>&1 | head -50
```

Expected: Tests should initialize browser without download errors. If tests timeout waiting for browser, verify `/usr/bin/chromium-browser --version` runs manually first.

- [ ] **Step 4: Create integration test verifying browser initialization**

Add to `tests/test_browser_setup.py`:

```python
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
```

- [ ] **Step 5: Run integration test**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/test_browser_setup.py::test_playwright_browser_initializes_with_manual_chromium -v -s
```

Expected output:
```
tests/test_browser_setup.py::test_playwright_browser_initializes_with_manual_chromium PASSED
```

- [ ] **Step 6: Commit**

```bash
cd /home/fahim/linkedin-scraper
git add conftest.py tests/test_browser_setup.py
git commit -m "feat: integrate browser config with Playwright fixtures"
```

---

### Task 4: Verify Full Test Suite Runs

**Files:**
- No changes, verification only

- [ ] **Step 1: Run all tests with verbose output**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests pass or fail for reasons unrelated to browser initialization.

- [ ] **Step 2: Run Playwright-specific tests**

```bash
cd /home/fahim/linkedin-scraper
python -m pytest tests/test_browser_setup.py -v
```

Expected:
```
tests/test_browser_setup.py::test_chromium_executable_exists PASSED
tests/test_browser_setup.py::test_chromium_executable_is_executable PASSED
tests/test_browser_setup.py::test_chromium_returns_version PASSED
tests/test_browser_setup.py::test_validate_chromium_executable_success PASSED
tests/test_browser_setup.py::test_validate_chromium_executable_with_missing_path PASSED
tests/test_browser_setup.py::test_env_file_skip_download_set PASSED
tests/test_browser_setup.py::test_env_file_chromium_path_set PASSED
tests/test_browser_setup.py::test_playwright_browser_initializes_with_manual_chromium PASSED

===== 8 passed in 2.30s =====
```

- [ ] **Step 3: Verify no `python -m playwright install` needed**

```bash
cd /home/fahim/linkedin-scraper
# This should now NOT try to download browsers
python -m playwright install --with-deps 2>&1 | grep -i "skipping\|already\|not needed" || echo "Check output above for status"
```

- [ ] **Step 4: Document setup in README**

Add to project README.md under "Setup" or "Development":

```markdown
### Playwright Setup (Ubuntu 26.04 with Manual Chromium)

This project uses a manually installed Chromium browser at `/usr/bin/chromium-browser` due to missing system dependencies in Ubuntu 26.04.

**Installation:**
1. Install Chromium: `sudo apt-get install chromium-browser` (or verify it's already at `/usr/bin/chromium-browser`)
2. Install Python dependencies: `pip install -r requirements.txt`
3. Tests use `.env.test` which sets `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`
4. Run tests normally: `pytest tests/`

**Troubleshooting:**
- If Chromium not found, verify: `which chromium-browser` or `ls -la /usr/bin/chromium-browser`
- If "permission denied", fix with: `chmod +x /usr/bin/chromium-browser`
- If test hangs on browser launch, check system dependencies with: `/usr/bin/chromium-browser --version`
```

- [ ] **Step 5: Final commit**

```bash
cd /home/fahim/linkedin-scraper
git add README.md
git commit -m "docs: add Playwright setup instructions for Ubuntu 26.04 manual Chromium"
```

---

## State Management Strategy

- **Browser Executable Path:** Discovered once per test session via `get_chromium_executable_path()`, cached in environment variable `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`
- **Launch Args:** Generated per browser instance via `get_browser_launch_args()`, includes validated executable path
- **Fixtures:** Session-scoped browser, function-scoped page/context (standard Playwright pattern)
- **No State Mutation:** Environment variables loaded once at pytest startup, not modified during tests

---

## Accessibility Considerations

- Error messages include specific file paths and remediation steps (chmod, apt-get commands)
- Validation functions provide clear, actionable exceptions instead of silent failures
- `.env.test` documents purpose of each variable
- README includes troubleshooting section with exact commands

---

## Test Plan

| Test | File | Purpose |
|------|------|---------|
| `test_chromium_executable_exists` | `tests/test_browser_setup.py` | Verify `/usr/bin/chromium-browser` file exists |
| `test_chromium_executable_is_executable` | `tests/test_browser_setup.py` | Verify execute permission set |
| `test_chromium_returns_version` | `tests/test_browser_setup.py` | Verify Chromium responds to `--version` |
| `test_validate_chromium_executable_success` | `tests/test_browser_setup.py` | Verify validation function succeeds |
| `test_validate_chromium_executable_with_missing_path` | `tests/test_browser_setup.py` | Verify validation handles missing executable |
| `test_env_file_skip_download_set` | `tests/test_browser_setup.py` | Verify environment disables downloads |
| `test_env_file_chromium_path_set` | `tests/test_browser_setup.py` | Verify explicit path set in environment |
| `test_playwright_browser_initializes_with_manual_chromium` | `tests/test_browser_setup.py` | Verify Playwright can launch and use Chromium |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Chromium not at `/usr/bin/chromium-browser` | Fallback checks common alternative paths; raises clear error with installation command |
| Chromium executable missing permission | Validation catches and suggests `chmod +x`, error message is actionable |
| Different Ubuntu version has Chromium at different path | Add custom path check in `get_chromium_executable_path()` if needed, environment variable `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can override |
| Test hangs on browser launch | Browser validation runs before test, catches issues early |
| Playwright still tries to download | `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in `.env.test` forces skip; pytest_configure ensures it's set |
| Existing tests assume Playwright downloads browsers | No existing code changes required—fixtures override behavior transparently |

---

## Acceptance Checklist

- [ ] `src/browser_config.py` created with executable discovery and validation
- [ ] `tests/test_browser_setup.py` created with 8 passing tests
- [ ] `.env.test` created with required environment variables
- [ ] `conftest.py` modified to load environment and inject browser launch args
- [ ] All tests in suite pass without `python -m playwright install` downloads
- [ ] Manual Chromium at `/usr/bin/chromium-browser` is used for all test browser instances
- [ ] Error messages provide actionable remediation (specific file paths, commands)
- [ ] README updated with setup and troubleshooting instructions
- [ ] All changes committed with descriptive messages

---
