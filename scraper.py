"""
Core LinkedIn profile scraper with humanized interaction patterns.

Provides organic profile traversal with stealth configuration, randomized
delays, and simulated user interactions to avoid bot detection.
"""

import random
import time
import logging
import os
from typing import Optional, Dict, List
from urllib.parse import urljoin

from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import Stealth


logger = logging.getLogger(__name__)


# Ubuntu Chromium environment configuration for headless Linux execution
CHROMIUM_LAUNCH_ENV = {
    "DISPLAY": os.environ.get("DISPLAY", ":99"),  # Xvfb for headless
    "PATH": os.environ.get("PATH", ""),
}


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
        profile_data = await extract_profile_metadata(page, profile_url)

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
