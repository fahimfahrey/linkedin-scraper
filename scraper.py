"""
Core LinkedIn profile scraper with humanized interaction patterns.

Provides organic profile traversal with stealth configuration, randomized
delays, and simulated user interactions to avoid bot detection.
"""

import random
import time
import logging
import os
import json
import re
import queue
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, List, Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

from queue_protocol import StatusUpdate, ProfilePayload, OperationWarning, ExecutionComplete
from environment_config import get_chromium_environment

logger = logging.getLogger(__name__)


# === Custom Exceptions ===

class ExecutionWindowExceeded(Exception):
    """Raised when daily profile limit reached."""
    pass


class SecurityIncidentDetected(Exception):
    """Raised when anomaly interception triggered."""
    def __init__(self, anomaly_type: str, details: dict):
        self.anomaly_type = anomaly_type
        self.details = details
        super().__init__(f"Security incident: {anomaly_type}")


# Ubuntu Chromium environment configuration for headless Linux execution
CHROMIUM_LAUNCH_ENV = get_chromium_environment()


# === Anti-Ban Guardrails ===

class SystemStateSnapshot:
    """Captures runtime state at incident time for forensics."""

    def __init__(
        self,
        profiles_collected: int,
        anomaly_type: str,
        anomaly_details: dict,
        browser_url: str = "",
        page_title: str = "",
        memory_usage_mb: float = 0.0,
        execution_duration_sec: float = 0.0,
    ):
        self.timestamp = datetime.now().isoformat()
        self.profiles_collected = profiles_collected
        self.anomaly_type = anomaly_type
        self.anomaly_details = anomaly_details
        self.browser_url = browser_url
        self.page_title = page_title
        self.memory_usage_mb = memory_usage_mb
        self.execution_duration_sec = execution_duration_sec

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "profiles_collected": self.profiles_collected,
            "anomaly_type": self.anomaly_type,
            "anomaly_details": self.anomaly_details,
            "browser_url": self.browser_url,
            "page_title": self.page_title,
            "memory_usage_mb": self.memory_usage_mb,
            "execution_duration_sec": self.execution_duration_sec,
        }

    def to_json_line(self) -> str:
        """Convert to JSON string for line-based logging."""
        import json
        return json.dumps(self.to_dict())


class ExecutionWindowController:
    """Tracks daily profile count and enforces hard limits with graduated warnings."""

    def __init__(self, max_profiles_per_day: int = 45, state_file: str = "execution_window.json"):
        self.max_profiles_per_day = max_profiles_per_day
        self.state_file = state_file
        self.state = self._load_state()
        self.soft_warning_threshold = int(max_profiles_per_day * 0.8)  # 80%
        self.critical_warning_threshold = int(max_profiles_per_day * 0.9)  # 90%

    def _load_state(self) -> dict:
        """Load state from JSON file, handle missing/corrupted files."""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, "r") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state file {self.state_file}: {e}. Reinitializing.")
        return {"date": str(date.today()), "count": 0, "reset_count": 0}

    def _save_state(self) -> None:
        """Save state to JSON file atomically."""
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save state: {e}")

    async def reset_if_new_day(self) -> None:
        """Check date, reset counter if new day detected."""
        today = str(date.today())
        if self.state.get("date") != today:
            self.state = {"date": today, "count": 0, "reset_count": self.state.get("reset_count", 0) + 1}
            self._save_state()
            logger.info(f"Execution window reset: new day detected. Reset count: {self.state['reset_count']}")

    def get_state(self) -> dict:
        """Export current state for snapshots and forensics."""
        return {
            "date": self.state.get("date"),
            "count": self.state.get("count", 0),
            "reset_count": self.state.get("reset_count", 0),
            "max_profiles": self.max_profiles_per_day,
        }

    async def increment_reset_count(self) -> None:
        """Increment daily reset counter."""
        self.state["reset_count"] = self.state.get("reset_count", 0) + 1
        self._save_state()

    async def check_and_increment(self) -> bool:
        """
        Increment counter, emit graduated warnings, check if under limit.

        Raises:
            ExecutionWindowExceeded: If at or over hard limit.
        """
        await self.reset_if_new_day()

        if self.state["count"] >= self.max_profiles_per_day:
            logger.critical(f"HARD LIMIT EXCEEDED: {self.state['count']}/{self.max_profiles_per_day}")
            raise ExecutionWindowExceeded(
                f"Daily profile limit ({self.max_profiles_per_day}) exceeded"
            )

        self.state["count"] += 1

        # Graduated warnings
        if self.state["count"] == self.critical_warning_threshold:
            logger.warning(
                f"CRITICAL: {self.state['count']}/{self.max_profiles_per_day} profiles. "
                f"Only {self.max_profiles_per_day - self.state['count']} remaining."
            )
        elif self.state["count"] == self.soft_warning_threshold:
            logger.warning(
                f"WARNING: {self.state['count']}/{self.max_profiles_per_day} profiles (80% threshold). "
                f"{self.max_profiles_per_day - self.state['count']} profiles remaining."
            )

        self._save_state()
        return True


class AnomalyDetector:
    """Detects suspicious platform responses with multi-vector detection."""

    def __init__(self, url_history_limit: int = 10):
        # Precompile regex patterns for performance
        self.captcha_pattern = re.compile(r"recaptcha|hcaptcha|challenge|verify.*identity", re.IGNORECASE)
        self.logout_pattern = re.compile(r"sign.?in|log.?in|authenticate", re.IGNORECASE)
        self.rate_limit_pattern = re.compile(
            r"rate.?limit|too.?many|slow.?down|try.?again|429|503", re.IGNORECASE
        )
        self.known_paths = {"/in/", "/company/", "/search/", "/jobs/"}
        self.url_history_limit = url_history_limit
        self.url_history = []
        self.rate_limit_failure_count = 0

    async def inspect_page(self, page: Page) -> Optional[str]:
        """Run all detection patterns on page. Returns anomaly type or None."""
        try:
            page_content = await page.content()
            page_url = page.url
            page_title = await page.title()

            self._track_url(page_url)

            # Check for CAPTCHA
            if self._detect_captcha(page_content, page_url, page_title):
                logger.critical("SECURITY INCIDENT: CAPTCHA detected. Emergency shutdown initiated.")
                return "captcha"

            # Check for forced logout
            if self._detect_logout(page_url, page_title):
                logger.critical("SECURITY INCIDENT: Forced logout detected. Emergency shutdown initiated.")
                return "forced_logout"

            # Check for rate limit
            if self._detect_rate_limit(page_content):
                self.rate_limit_failure_count += 1
                if self.rate_limit_failure_count >= 2:
                    logger.critical("SECURITY INCIDENT: Rate limit detected. Emergency shutdown initiated.")
                    return "rate_limit"
            else:
                self.reset_failure_count()

            # Check for redirect anomaly
            if self._detect_redirect_anomaly(page_url):
                logger.critical("SECURITY INCIDENT: Redirect anomaly detected. Emergency shutdown initiated.")
                return "redirect_anomaly"

            return None
        except Exception as e:
            logger.warning(f"Anomaly detection failed: {e}")
            return None

    def _track_url(self, url: str) -> None:
        """Maintain rolling URL history."""
        self.url_history.append(url)
        if len(self.url_history) > self.url_history_limit:
            self.url_history.pop(0)

    def reset_failure_count(self) -> None:
        """Reset consecutive failure counter after successful page load."""
        self.rate_limit_failure_count = 0

    def _detect_captcha(self, page_content: str, page_url: str, page_title: str) -> bool:
        """Detect CAPTCHA iframe or challenge elements."""
        if self.captcha_pattern.search(page_content):
            return True
        if "challenge" in page_url.lower():
            return True
        if "verify" in page_title.lower() or "security" in page_title.lower():
            return True
        return False

    def _detect_logout(self, page_url: str, page_title: str) -> bool:
        """Detect forced logout (URL/title patterns)."""
        if "/login" in page_url or "/signup" in page_url or "/auth" in page_url:
            return True
        if self.logout_pattern.search(page_title):
            return True
        return False

    def _detect_rate_limit(self, page_content: str) -> bool:
        """Detect rate limit text in page."""
        return bool(self.rate_limit_pattern.search(page_content))

    def _detect_redirect_anomaly(self, current_url: str) -> bool:
        """Detect deviation from known paths using URL history."""
        is_valid = any(path in current_url for path in self.known_paths)
        if not is_valid and len(self.url_history) > 1:
            prev_url = self.url_history[-2]
            if prev_url != current_url and "linkedin.com" in current_url:
                if "/error" in current_url or "session" in current_url or "/auth/" in current_url:
                    return True
        return False


class EmergencyShutdown:
    """Orchestrates graceful termination with data persistence and logging."""

    def __init__(
        self,
        incident_type: str,
        details: dict,
        profiles_buffer: List[Dict],
        db_path: str = "linkedin_profiles.db",
    ):
        self.incident_type = incident_type
        self.details = details
        self.profiles_buffer = profiles_buffer
        self.db_path = db_path

    async def execute(
        self,
        browser,
        context,
        page,
        window_controller: Optional[ExecutionWindowController],
        start_time: float,
    ) -> None:
        """
        Execute emergency shutdown sequence: Flush → Log → Cleanup.
        Order is critical for data integrity.
        """
        try:
            # Phase 1: Flush profiles to SQLite
            await self._flush_profiles()

            # Phase 2: Log incident state
            if window_controller:
                await self._log_incident_state(window_controller, start_time, page)

            # Phase 3: Cleanup browser
            await self._cleanup_browser(browser, context)

            logger.info(f"Emergency shutdown complete: {self.incident_type}")
        except Exception as e:
            logger.error(f"Error during emergency shutdown: {e}", exc_info=True)

    async def _flush_profiles(self) -> None:
        """Atomically write collected profiles to SQLite."""
        if not self.profiles_buffer:
            logger.info("No profiles to flush")
            return

        try:
            import asyncio
            from database import insert_profile_batch

            # Run DB insert in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, insert_profile_batch, self.profiles_buffer)
            logger.info(f"Flushed {len(self.profiles_buffer)} profiles to database")
        except Exception as e:
            logger.error(f"Failed to flush profiles: {e}", exc_info=True)

    async def _log_incident_state(
        self,
        window_controller: ExecutionWindowController,
        start_time: float,
        page: Optional[Page],
    ) -> None:
        """Serialize system state snapshot to security_incidents.log."""
        try:
            page_url = page.url if page else "N/A"
            page_title = (await page.title()) if page else "N/A"

            # Calculate memory usage
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            snapshot = SystemStateSnapshot(
                profiles_collected=len(self.profiles_buffer),
                anomaly_type=self.incident_type,
                anomaly_details=self.details,
                browser_url=page_url,
                page_title=page_title,
                memory_usage_mb=memory_mb,
                execution_duration_sec=time.time() - start_time,
            )

            # Append to security_incidents.log as JSON line
            with open("security_incidents.log", "a") as f:
                f.write(snapshot.to_json_line() + "\n")

            logger.info(f"Incident state logged to security_incidents.log")
        except Exception as e:
            logger.error(f"Failed to log incident state: {e}", exc_info=True)

    async def _cleanup_browser(self, browser, context) -> None:
        """Close browser resources. Wraps exceptions but continues."""
        try:
            if context:
                await context.close()
                logger.debug("Browser context closed")
        except Exception as e:
            logger.warning(f"Context close failed: {e}")

        try:
            if browser:
                await browser.close()
                logger.debug("Browser closed")
        except Exception as e:
            logger.warning(f"Browser close failed: {e}")
            # Fallback: attempt OS-level process termination
            try:
                import subprocess
                import psutil

                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        if "chrome" in proc.info["name"].lower():
                            proc.terminate()
                            logger.info(f"Terminated orphaned process: {proc.info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except ImportError:
                logger.warning("psutil not available for fallback cleanup")


async def safe_browser_cleanup(browser, context) -> None:
    """
    Gracefully close browser and context. Fallback to OS-level termination if needed.

    Never raises exceptions — logs errors and continues.
    """
    try:
        if context:
            await context.close()
            logger.debug("Browser context closed")
    except Exception as e:
        logger.warning(f"Context close failed: {e}")

    try:
        if browser:
            await browser.close()
            logger.debug("Browser closed")
    except Exception as e:
        logger.warning(f"Browser close failed: {e}")
        # Fallback: attempt OS-level process termination
        try:
            import subprocess
            import psutil

            # Find Chromium process by parent/name
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if "chrome" in proc.info["name"].lower():
                        proc.terminate()
                        logger.info(f"Terminated orphaned process: {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            logger.warning("psutil not available for fallback cleanup")


# Module-level singletons
_WINDOW_CONTROLLER: Optional[ExecutionWindowController] = None
_ANOMALY_DETECTOR: Optional[AnomalyDetector] = None


async def _init_controllers() -> None:
    """Initialize global controllers on first use."""
    global _WINDOW_CONTROLLER, _ANOMALY_DETECTOR
    if _WINDOW_CONTROLLER is None:
        _WINDOW_CONTROLLER = ExecutionWindowController()
        _ANOMALY_DETECTOR = AnomalyDetector()
    await _WINDOW_CONTROLLER.reset_if_new_day()


async def launch_stealth_browser():
    """
    Launch Chromium browser with playwright-stealth configuration.

    Applies anti-bot detection measures and Ubuntu-specific environment setup
    for reliable execution on Linux architectures.

    Returns:
        Tuple of (async_playwright instance, Browser instance).

    Raises:
        RuntimeError: If browser launch fails.
    """
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--single-process",
            ],
            env=CHROMIUM_LAUNCH_ENV,
        )
        logger.info("Stealth browser launched successfully")
        return p, browser
    except Exception as e:
        logger.error(f"Failed to launch stealth browser: {e}")
        raise RuntimeError(f"Browser launch failed: {e}") from e


async def create_stealth_context(browser) -> BrowserContext:
    """
    Create a browser context with stealth configuration.

    Applies playwright-stealth patches to hide automation indicators
    and mimic natural browser behavior.

    Args:
        browser: Playwright Browser instance.

    Returns:
        BrowserContext with stealth configuration applied.
    """
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
    )
    stealth = Stealth()
    await stealth.apply_stealth_async(context)
    logger.info("Stealth context created with evasion patches")
    return context


def humanized_sleep(min_secs: float = 3.5, max_secs: float = 7.8) -> None:
    """
    Sleep for randomized duration to mimic human behavior.

    Prevents bot detection by introducing variable delays between actions.

    Args:
        min_secs: Minimum sleep duration in seconds. Defaults to 3.5.
        max_secs: Maximum sleep duration in seconds. Defaults to 7.8.
    """
    duration = random.uniform(min_secs, max_secs)
    time.sleep(duration)
    logger.debug(f"Humanized sleep: {duration:.2f}s")


async def simulate_mouse_movement(page: Page) -> None:
    """
    Simulate organic mouse movement across page.

    Performs random mouse moves to appear as natural user interaction.

    Args:
        page: Playwright Page instance.
    """
    try:
        # Move mouse to random position on page
        x = random.randint(100, 1800)
        y = random.randint(100, 900)
        await page.mouse.move(x, y)
        await page.mouse.move(x + random.randint(10, 50), y + random.randint(10, 50))
        logger.debug(f"Mouse movement simulated to ({x}, {y})")
    except Exception as e:
        logger.warning(f"Mouse movement simulation failed: {e}")


async def simulate_keyboard_action(page: Page) -> None:
    """
    Simulate keyboard interaction (scroll with keyboard).

    Adds naturalistic keyboard input to interaction pattern.

    Args:
        page: Playwright Page instance.
    """
    try:
        # Random keyboard action (Page Down or arrow keys)
        key = random.choice(["PageDown", "ArrowDown", "ArrowDown"])
        await page.keyboard.press(key)
        logger.debug(f"Keyboard action simulated: {key}")
    except Exception as e:
        logger.warning(f"Keyboard simulation failed: {e}")


async def scroll_profile_page(page: Page, step_range: tuple = (300, 500)) -> None:
    """
    Scroll profile page incrementally to trigger lazy-load hydration.

    Performs viewport scrolling in randomized steps, allowing async components
    and lazy-loaded images to fully render.

    Args:
        page: Playwright Page instance.
        step_range: Tuple of (min_px, max_px) for scroll step size.
    """
    try:
        # Get current scroll height
        scroll_height = await page.evaluate("document.documentElement.scrollHeight")
        current_scroll = 0

        while current_scroll < scroll_height:
            # Randomize scroll step within range
            step = random.randint(step_range[0], step_range[1])
            current_scroll += step

            # Scroll down
            await page.evaluate(f"window.scrollBy(0, {step})")
            logger.debug(f"Scrolled {step}px (total: {current_scroll}px)")

            # Humanized pause between scrolls
            humanized_sleep(1.5, 3.5)

            # Update scroll height (content may have loaded)
            scroll_height = await page.evaluate("document.documentElement.scrollHeight")

        logger.info("Profile page scrolling complete")
    except Exception as e:
        logger.error(f"Scroll failed: {e}")


async def click_see_more_buttons(page: Page, section: str = "all") -> int:
    """
    Locate and click 'See more' buttons across profile sections.

    Searches for and clicks expandable content buttons in experience,
    education, and other sections to reveal full profile information.

    Args:
        page: Playwright Page instance.
        section: Target section ('experience', 'education', 'all'). Defaults to 'all'.

    Returns:
        Number of 'See more' buttons clicked.
    """
    clicks = 0
    try:
        # Selectors for 'See more' buttons across LinkedIn sections
        selectors = [
            "button:has-text('See more')",
            "button[aria-label*='Show more']",
            "button[aria-label*='Show less']",
            "text=See more",
        ]

        for selector in selectors:
            try:
                buttons = await page.query_selector_all(selector)
                for button in buttons:
                    try:
                        # Check if button is visible
                        is_visible = await button.is_visible()
                        if is_visible:
                            await button.click()
                            clicks += 1
                            logger.info(f"Clicked 'See more' button ({clicks})")
                            humanized_sleep(2.0, 4.0)
                    except Exception as e:
                        logger.debug(f"Failed to click button: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Selector not found: {selector}")
                continue

        logger.info(f"Total 'See more' buttons clicked: {clicks}")
        return clicks
    except Exception as e:
        logger.error(f"Error clicking 'See more' buttons: {e}")
        return clicks


async def traverse_profile(
    context: BrowserContext,
    profile_url: str,
    expand_all: bool = True,
) -> Dict[str, any]:
    """
    Traverse LinkedIn profile with humanized interactions.

    Core routine that accepts authenticated browser context and profile URL,
    then performs organic profile scrolling, clicking, and data extraction
    while avoiding bot detection.

    Args:
        context: Authenticated BrowserContext from SessionManager.
        profile_url: Target LinkedIn profile URL.
        expand_all: Whether to expand all sections. Defaults to True.

    Returns:
        Dictionary containing extracted profile data.

    Raises:
        ValueError: If profile_url is invalid.
        RuntimeError: If page navigation fails.
    """
    if not profile_url or not isinstance(profile_url, str):
        raise ValueError("profile_url must be a non-empty string")

    page = None
    try:
        page = await context.new_page()
        logger.info(f"Navigating to profile: {profile_url}")

        # Navigate to profile with timeout
        await page.goto(profile_url, wait_until="networkidle", timeout=30000)
        logger.info("Profile page loaded")

        # Anomaly detection post-navigation
        anomaly = await _ANOMALY_DETECTOR.inspect_page(page)
        if anomaly:
            raise SecurityIncidentDetected(anomaly, {
                "profile_url": profile_url,
                "page_url": page.url,
                "timestamp": datetime.now().isoformat()
            })

        # Simulate initial user behavior
        humanized_sleep(2.0, 4.5)
        await simulate_mouse_movement(page)

        # Scroll page to trigger lazy-load and initial content hydration
        logger.info("Beginning incremental scroll to hydrate content")
        await scroll_profile_page(page, step_range=(300, 500))

        # Expand all sections if requested
        if expand_all:
            logger.info("Expanding all profile sections")
            await click_see_more_buttons(page, section="all")

        # Final scroll to ensure all content loaded
        await scroll_profile_page(page, step_range=(200, 400))

        # Extract basic profile metadata
        profile_data = await extract_profile_with_beautifulsoup(page, profile_url)

        logger.info(f"Profile traversal complete for {profile_url}")
        return profile_data

    except RuntimeError as e:
        logger.error(f"Runtime error during profile traversal: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during profile traversal: {e}")
        raise RuntimeError(f"Profile traversal failed: {e}") from e
    finally:
        if page:
            await page.close()


def extract_full_name(soup: BeautifulSoup, default: str = "") -> str:
	"""
	Extract full name from profile using semantic containers.

	Tries multiple extraction strategies:
	1. h1 tag (primary semantic header)
	2. JSON-LD Person schema
	3. Open Graph name meta tag
	4. aria-labeled heading elements

	Args:
		soup: BeautifulSoup object of parsed HTML
		default: Default value if extraction fails

	Returns:
		Extracted full name or default
	"""
	try:
		# Strategy 1: Primary h1 heading
		h1 = soup.select_one("h1")
		if h1:
			name = h1.get_text(strip=True)
			if name and len(name) > 1:
				logger.debug(f"Name extracted from h1: {name}")
				return name
	except Exception as e:
		logger.debug(f"h1 extraction failed: {e}")

	try:
		# Strategy 2: JSON-LD Person schema
		ld_json = soup.find("script", {"type": "application/ld+json"})
		if ld_json:
			data = json.loads(ld_json.string)
			if isinstance(data, dict) and "name" in data:
				name = data.get("name", "").strip()
				if name:
					logger.debug(f"Name extracted from JSON-LD: {name}")
					return name
	except Exception as e:
		logger.debug(f"JSON-LD extraction failed: {e}")

	try:
		# Strategy 3: Open Graph meta tag
		og_name = soup.select_one("meta[property='og:title']")
		if og_name:
			name = og_name.get("content", "").strip()
			if name:
				logger.debug(f"Name extracted from og:title: {name}")
				return name
	except Exception as e:
		logger.debug(f"og:title extraction failed: {e}")

	logger.warning("Full name extraction failed, returning default")
	return default


def extract_headline(soup: BeautifulSoup, default: str = "") -> str:
	"""
	Extract headline (job title + company) from profile.

	Tries multiple extraction strategies:
	1. Semantic div with id containing 'headline'
	2. JSON-LD jobTitle field
	3. Meta description prefix
	4. Paragraph following h1

	Args:
		soup: BeautifulSoup object of parsed HTML
		default: Default value if extraction fails

	Returns:
		Extracted headline or default
	"""
	try:
		# Strategy 1: Semantic headline container
		headline_div = soup.select_one("div[id*='headline']")
		if headline_div:
			headline = headline_div.get_text(strip=True)
			if headline and len(headline) > 2:
				logger.debug(f"Headline extracted from semantic div: {headline}")
				return headline
	except Exception as e:
		logger.debug(f"Semantic headline extraction failed: {e}")

	try:
		# Strategy 2: JSON-LD jobTitle
		ld_json = soup.find("script", {"type": "application/ld+json"})
		if ld_json:
			data = json.loads(ld_json.string)
			job_title = data.get("jobTitle", "").strip()
			if job_title:
				logger.debug(f"Headline extracted from JSON-LD: {job_title}")
				return job_title
	except Exception as e:
		logger.debug(f"JSON-LD jobTitle extraction failed: {e}")

	try:
		# Strategy 3: Meta description (often contains headline)
		meta_desc = soup.select_one("meta[name='description']")
		if meta_desc:
			desc = meta_desc.get("content", "").strip()
			if desc and len(desc) > 5:
				# Extract first sentence/clause as headline
				headline = desc.split(" | ")[0].strip()
				logger.debug(f"Headline extracted from meta: {headline}")
				return headline
	except Exception as e:
		logger.debug(f"Meta description extraction failed: {e}")

	try:
		# Strategy 4: Paragraph following h1
		h1 = soup.select_one("h1")
		if h1:
			p = h1.find_next("p")
			if p:
				headline = p.get_text(strip=True)
				if headline:
					logger.debug(f"Headline extracted from post-h1 paragraph: {headline}")
					return headline
	except Exception as e:
		logger.debug(f"Post-h1 paragraph extraction failed: {e}")

	logger.warning("Headline extraction failed, returning default")
	return default


def extract_current_workplace(soup: BeautifulSoup, default: str = "") -> str:
	"""
	Extract current workplace/company from profile.

	Tries multiple extraction strategies:
	1. JSON-LD worksFor.name
	2. Semantic experience section current company
	3. og:site_name
	4. Strong tags in experience container

	Args:
		soup: BeautifulSoup object of parsed HTML
		default: Default value if extraction fails

	Returns:
		Extracted current workplace or default
	"""
	try:
		# Strategy 1: JSON-LD worksFor
		ld_json = soup.find("script", {"type": "application/ld+json"})
		if ld_json:
			data = json.loads(ld_json.string)
			works_for = data.get("worksFor", {})
			if isinstance(works_for, dict):
				company = works_for.get("name", "").strip()
			elif isinstance(works_for, list) and works_for:
				company = works_for[0].get("name", "").strip() if isinstance(works_for[0], dict) else ""
			else:
				company = ""

			if company:
				logger.debug(f"Workplace extracted from JSON-LD: {company}")
				return company
	except Exception as e:
		logger.debug(f"JSON-LD worksFor extraction failed: {e}")

	try:
		# Strategy 2: Experience section with 'current' marker
		exp_section = soup.select_one("section[id*='experience']")
		if exp_section:
			# Look for current employment indicators
			current = exp_section.select_one("[class*='current'], [data-test*='current']")
			if current:
				company = current.get_text(strip=True)
				if company:
					logger.debug(f"Workplace extracted from experience section: {company}")
					return company
	except Exception as e:
		logger.debug(f"Experience section extraction failed: {e}")

	try:
		# Strategy 3: Strong tag in experience (often company name)
		exp_section = soup.select_one("section[id*='experience']")
		if exp_section:
			strong = exp_section.select_one("strong")
			if strong:
				company = strong.get_text(strip=True)
				if company and len(company) > 1:
					logger.debug(f"Workplace extracted from strong tag: {company}")
					return company
	except Exception as e:
		logger.debug(f"Strong tag extraction failed: {e}")

	logger.warning("Workplace extraction failed, returning default")
	return default


def extract_jobs_array(soup: BeautifulSoup, default: List[Dict[str, str]] = None) -> List[Dict[str, str]]:
	"""
	Extract array of job positions from experience section.

	Parses experience section for structured job data:
	- job title
	- company name
	- duration/dates
	- description (if available)

	Args:
		soup: BeautifulSoup object of parsed HTML
		default: Default value if extraction fails

	Returns:
		List of job dictionaries or default empty list
	"""
	if default is None:
		default = []

	try:
		# Strategy 1: JSON-LD workHistory
		ld_json = soup.find("script", {"type": "application/ld+json"})
		if ld_json:
			data = json.loads(ld_json.string)
			work_history = data.get("workHistory", [])
			if work_history and isinstance(work_history, list):
				jobs = []
				for job in work_history:
					if isinstance(job, dict):
						jobs.append({
							"title": job.get("position", ""),
							"company": job.get("organization", {}).get("name", "") if isinstance(job.get("organization"), dict) else "",
							"duration": f"{job.get('startDate', '')} - {job.get('endDate', '')}",
							"description": job.get("description", "")
						})
				if jobs:
					logger.debug(f"Extracted {len(jobs)} jobs from JSON-LD")
					return jobs
	except Exception as e:
		logger.debug(f"JSON-LD workHistory extraction failed: {e}")

	try:
		# Strategy 2: Experience section list items
		exp_section = soup.select_one("section[id*='experience'], div[id*='experience']")
		if exp_section:
			job_items = exp_section.select("li, div[class*='experience-item'], article")
			jobs = []

			for item in job_items:
				try:
					title_elem = item.select_one("h3, strong, [class*='title']")
					company_elem = item.select_one("[class*='company'], span:nth-of-type(2)")
					duration_elem = item.select_one("[class*='date'], span:nth-of-type(3)")

					job = {
						"title": title_elem.get_text(strip=True) if title_elem else "",
						"company": company_elem.get_text(strip=True) if company_elem else "",
						"duration": duration_elem.get_text(strip=True) if duration_elem else "",
						"description": ""
					}

					if job["title"] or job["company"]:
						jobs.append(job)
				except Exception as item_err:
					logger.debug(f"Job item parsing failed: {item_err}")
					continue

			if jobs:
				logger.debug(f"Extracted {len(jobs)} jobs from experience section")
				return jobs
	except Exception as e:
		logger.debug(f"Experience section extraction failed: {e}")

	logger.warning("Jobs array extraction failed, returning default")
	return default


def extract_schools_array(soup: BeautifulSoup, default: List[Dict[str, str]] = None) -> List[Dict[str, str]]:
	"""
	Extract array of education entries from education section.

	Parses education section for structured school data:
	- school name
	- degree
	- field of study
	- graduation year
	- activities/societies

	Args:
		soup: BeautifulSoup object of parsed HTML
		default: Default value if extraction fails

	Returns:
		List of school dictionaries or default empty list
	"""
	if default is None:
		default = []

	try:
		# Strategy 1: JSON-LD alumniOf / educationDetails
		ld_json = soup.find("script", {"type": "application/ld+json"})
		if ld_json:
			data = json.loads(ld_json.string)

			# Try alumniOf first
			alumni_of = data.get("alumniOf", [])
			if alumni_of and isinstance(alumni_of, list):
				schools = []
				for school in alumni_of:
					if isinstance(school, dict):
						schools.append({
							"school": school.get("name", ""),
							"degree": school.get("degree", ""),
							"field": school.get("field", ""),
							"year": school.get("year", "")
						})
				if schools:
					logger.debug(f"Extracted {len(schools)} schools from JSON-LD alumniOf")
					return schools
	except Exception as e:
		logger.debug(f"JSON-LD alumniOf extraction failed: {e}")

	try:
		# Strategy 2: Education section list items
		edu_section = soup.select_one("section[id*='education'], div[id*='education']")
		if edu_section:
			school_items = edu_section.select("li, div[class*='education-item'], article")
			schools = []

			for item in school_items:
				try:
					school_elem = item.select_one("h3, strong, [class*='school']")
					degree_elem = item.select_one("[class*='degree']")
					field_elem = item.select_one("[class*='field'], span:nth-of-type(2)")
					year_elem = item.select_one("[class*='year'], span:nth-of-type(3)")

					school = {
						"school": school_elem.get_text(strip=True) if school_elem else "",
						"degree": degree_elem.get_text(strip=True) if degree_elem else "",
						"field": field_elem.get_text(strip=True) if field_elem else "",
						"year": year_elem.get_text(strip=True) if year_elem else ""
					}

					if school["school"]:
						schools.append(school)
				except Exception as item_err:
					logger.debug(f"School item parsing failed: {item_err}")
					continue

			if schools:
				logger.debug(f"Extracted {len(schools)} schools from education section")
				return schools
	except Exception as e:
		logger.debug(f"Education section extraction failed: {e}")

	logger.warning("Schools array extraction failed, returning default")
	return default


async def extract_profile_with_beautifulsoup(page: Page, profile_url: str) -> Dict[str, Any]:
	"""
	Extract profile data using BeautifulSoup4 with lxml parser.

	Gets page HTML from Playwright and parses with BeautifulSoup,
	using high-reliability targets like JSON-LD and semantic containers
	instead of volatile CSS classes.

	Each extraction segment isolated in try/except to prevent single
	missing elements from crashing the pipeline.

	Args:
		page: Playwright Page instance after full traversal
		profile_url: Profile URL for reference

	Returns:
		Dictionary with extracted profile data
	"""
	profile_data = {
		"linkedin_url": profile_url,
		"full_name": "",
		"headline": "",
		"current_workplace": "",
		"location": "",
		"about_text": "",
		"jobs": [],
		"schools": [],
	}

	logger.info(f"Starting profile extraction for {profile_url}")

	try:
		# Get full page HTML from Playwright
		html_content = await page.content()
		soup = BeautifulSoup(html_content, "lxml")
		logger.debug("Page HTML parsed with BeautifulSoup lxml parser")

	except Exception as e:
		logger.error(f"Failed to parse page with BeautifulSoup: {e}")
		return profile_data

	# Extract full name with fail-safe closure
	try:
		profile_data["full_name"] = extract_full_name(soup)
	except Exception as e:
		logger.error(f"Full name extraction error: {e}")
		profile_data["full_name"] = ""

	# Extract headline with fail-safe closure
	try:
		profile_data["headline"] = extract_headline(soup)
	except Exception as e:
		logger.error(f"Headline extraction error: {e}")
		profile_data["headline"] = ""

	# Extract current workplace with fail-safe closure
	try:
		profile_data["current_workplace"] = extract_current_workplace(soup)
	except Exception as e:
		logger.error(f"Workplace extraction error: {e}")
		profile_data["current_workplace"] = ""

	# Extract location with fail-safe closure
	try:
		location_elem = soup.select_one("div[id*='location'], [data-test*='location'], span[class*='location']")
		if location_elem:
			profile_data["location"] = location_elem.get_text(strip=True)
	except Exception as e:
		logger.error(f"Location extraction error: {e}")
		profile_data["location"] = ""

	# Extract about section with fail-safe closure
	try:
		about_section = soup.select_one("section[id*='about'], div[id*='about']")
		if about_section:
			about_p = about_section.select_one("p")
			if about_p:
				profile_data["about_text"] = about_p.get_text(strip=True)
	except Exception as e:
		logger.error(f"About section extraction error: {e}")
		profile_data["about_text"] = ""

	# Extract jobs array with fail-safe closure
	try:
		profile_data["jobs"] = extract_jobs_array(soup)
	except Exception as e:
		logger.error(f"Jobs array extraction error: {e}")
		profile_data["jobs"] = []

	# Extract schools array with fail-safe closure
	try:
		profile_data["schools"] = extract_schools_array(soup)
	except Exception as e:
		logger.error(f"Schools array extraction error: {e}")
		profile_data["schools"] = []

	logger.info(f"Profile extraction complete: {profile_data.get('full_name', 'unknown')} from {profile_url}")
	return profile_data


async def extract_profile_metadata(page: Page, profile_url: str) -> Dict[str, any]:
    """
    Extract profile metadata from page.

    Safely extracts visible profile information after page has been
    fully scrolled and expanded.

    Args:
        page: Playwright Page instance after traversal.
        profile_url: Profile URL for reference.

    Returns:
        Dictionary with extracted metadata.
    """
    try:
        profile_data = {
            "linkedin_url": profile_url,
            "full_name": None,
            "headline": None,
            "location": None,
            "about_text": None,
            "experience_json": None,
            "education_json": None,
        }

        # Extract name
        try:
            name = await page.text_content("h1")
            if name:
                profile_data["full_name"] = name.strip()
        except Exception:
            pass

        # Extract headline
        try:
            headline = await page.text_content("[data-test-id='headline']")
            if headline:
                profile_data["headline"] = headline.strip()
        except Exception:
            pass

        # Extract location
        try:
            location = await page.text_content("[data-test-id='location']")
            if location:
                profile_data["location"] = location.strip()
        except Exception:
            pass

        # Extract about section
        try:
            about = await page.text_content("[data-test-id='about-section'] p")
            if about:
                profile_data["about_text"] = about.strip()
        except Exception:
            pass

        logger.info(f"Extracted metadata: {profile_data['full_name']} from {profile_url}")
        return profile_data

    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        return {
            "linkedin_url": profile_url,
            "full_name": None,
            "headline": None,
            "location": None,
            "about_text": None,
            "experience_json": None,
            "education_json": None,
        }


async def scrape_profile(context: BrowserContext, profile_url: str) -> Dict[str, any]:
    """
    Scrape LinkedIn profile using authenticated context.

    Convenience wrapper that handles profile traversal and returns
    structured profile data ready for database insertion.

    Args:
        context: Authenticated BrowserContext.
        profile_url: Target profile URL.

    Returns:
        Profile dictionary ready for database insertion.
    """
    return await traverse_profile(context, profile_url, expand_all=True)


async def _handle_security_incident(
    incident_type: str,
    details: dict,
    profiles_collected_buffer: List[Dict],
    browser,
    context,
    page,
    window_controller: Optional[ExecutionWindowController],
    start_time: float,
) -> None:
    """Centralized security incident handler. Orchestrates emergency shutdown."""
    try:
        shutdown = EmergencyShutdown(
            incident_type=incident_type,
            details=details,
            profiles_buffer=profiles_collected_buffer,
        )
        await shutdown.execute(browser, context, page, window_controller, start_time)
    except Exception as e:
        logger.error(f"Error handling security incident: {e}", exc_info=True)


async def scrape_profile_batch(
    urls: List[str],
    message_queue: queue.Queue,
    window_controller: ExecutionWindowController,
    anomaly_detector: AnomalyDetector,
    env: Optional[Dict[str, str]] = None,
    worker_id: str = "default",
    stop_event: Optional[threading.Event] = None,
) -> None:
    """
    Batch scrape LinkedIn profiles with safety guardrails.

    Enforces daily limits, detects anomalies, and gracefully shuts down
    with data persistence on security incidents or limit exceeded.

    Args:
        urls: List of LinkedIn profile URLs to scrape.
        message_queue: Thread-safe queue for status/payload messages.
        window_controller: ExecutionWindowController for daily limits.
        anomaly_detector: AnomalyDetector for security monitoring.
        env: OS environment dict for Chromium (overrides CHROMIUM_LAUNCH_ENV).
        worker_id: Worker ID for message correlation.
        stop_event: Threading event to signal graceful shutdown.
    """
    if env is None:
        env = CHROMIUM_LAUNCH_ENV

    p = None
    browser = None
    context = None
    page = None
    profiles_collected = 0
    profiles_buffer: List[Dict] = []
    start_time = time.time()
    incident_triggered = False

    try:
        # Initialize controllers
        await _init_controllers()

        # Launch browser
        p, browser = await launch_stealth_browser()
        context = await create_stealth_context(browser)
        logger.info(f"Browser launched for batch scrape ({len(urls)} profiles)")

        # Iterate profiles
        for idx, profile_url in enumerate(urls):
            if stop_event and stop_event.is_set():
                logger.info(f"Stop event received at profile {idx}/{len(urls)}")
                break

            try:
                # Emit status: loading
                status_msg = StatusUpdate(
                    worker_id=worker_id,
                    profile_url=profile_url,
                    status="loading",
                    elapsed_sec=time.time() - start_time,
                )
                message_queue.put(status_msg)

                # Check execution window before scrape
                await window_controller.check_and_increment()

                # Scrape profile
                profile_data = await scrape_profile(context, profile_url)
                page = context.pages[0] if context.pages else None

                # Check for anomalies after profile load
                anomaly = await anomaly_detector.inspect_page(page) if page else None
                if anomaly:
                    profiles_buffer.append(profile_data)
                    incident_triggered = True
                    raise SecurityIncidentDetected(anomaly, {"detected_during": "profile_scrape"})

                # Add to buffer for later flush
                profiles_buffer.append(profile_data)

                # Emit status: stored
                status_msg = StatusUpdate(
                    worker_id=worker_id,
                    profile_url=profile_url,
                    status="stored",
                    elapsed_sec=time.time() - start_time,
                )
                message_queue.put(status_msg)

                # Emit profile payload
                payload_msg = ProfilePayload(
                    worker_id=worker_id,
                    profile_data=profile_data,
                    url=profile_url,
                )
                message_queue.put(payload_msg)

                profiles_collected += 1
                logger.info(f"Profile {idx+1}/{len(urls)} collected: {profile_url}")

                # Humanized delay
                humanized_sleep(3.0, 5.0)

            except ExecutionWindowExceeded as e:
                logger.error(f"Execution window exceeded at profile {idx}: {e}")
                incident_triggered = True
                await _handle_security_incident(
                    incident_type="execution_window_exceeded",
                    details={"profile_index": idx, "limit_reached": window_controller.max_profiles_per_day},
                    profiles_collected_buffer=profiles_buffer,
                    browser=browser,
                    context=context,
                    page=page,
                    window_controller=window_controller,
                    start_time=start_time,
                )
                warn_msg = OperationWarning(
                    worker_id=worker_id,
                    severity="critical",
                    message=f"Daily limit reached: {str(e)}",
                    action="shutdown",
                )
                message_queue.put(warn_msg)
                break

            except SecurityIncidentDetected as e:
                logger.error(f"Security incident at profile {idx}: {e.anomaly_type}")
                await _handle_security_incident(
                    incident_type=e.anomaly_type,
                    details=e.details,
                    profiles_collected_buffer=profiles_buffer,
                    browser=browser,
                    context=context,
                    page=page,
                    window_controller=window_controller,
                    start_time=start_time,
                )
                warn_msg = OperationWarning(
                    worker_id=worker_id,
                    severity="critical",
                    message=f"Security incident: {e.anomaly_type}",
                    action="shutdown",
                )
                message_queue.put(warn_msg)
                break

            except Exception as e:
                logger.warning(f"Failed to scrape profile {idx} ({profile_url}): {e}")
                warn_msg = OperationWarning(
                    worker_id=worker_id,
                    severity="warning",
                    message=f"Profile scrape failed: {str(e)[:100]}",
                    action="continue",
                )
                message_queue.put(warn_msg)

        # Emit completion
        complete_msg = ExecutionComplete(
            worker_id=worker_id,
            success=not incident_triggered,
            profiles_collected=profiles_collected,
            total_queued=len(urls),
        )
        message_queue.put(complete_msg)
        logger.info(f"Batch scrape complete: {profiles_collected}/{len(urls)} collected")

    except Exception as e:
        logger.error(f"Batch scrape failed with fatal error: {e}", exc_info=True)
        complete_msg = ExecutionComplete(
            worker_id=worker_id,
            success=False,
            profiles_collected=profiles_collected,
            total_queued=len(urls),
            error_type=type(e).__name__,
            details={"error": str(e)},
        )
        message_queue.put(complete_msg)

    finally:
        # Cleanup browser
        await safe_browser_cleanup(browser, context)
        if p:
            await p.stop()
        logger.info(f"Worker {worker_id} cleanup complete")
