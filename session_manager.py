"""
Session manager for LinkedIn authentication and account persistence.

Handles interactive login with MFA support, session export/import, and validation
without storing hardcoded credentials.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


logger = logging.getLogger(__name__)


class SessionManager:
    """Manages LinkedIn session persistence and authentication flow."""

    def __init__(self, session_file: str = "session.json", mfa_timeout: int = 120000):
        """Initialize SessionManager.

        Args:
            session_file: Path to store session state JSON. Defaults to "session.json".
            mfa_timeout: Timeout in milliseconds for MFA completion. Defaults to 120000 (120s).
        """
        self.session_file = Path(session_file)
        self.mfa_timeout = mfa_timeout
        self.logger = logging.getLogger(__name__)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def launch_browser_for_login(self) -> Tuple[Browser, Page]:
        """Launch non-headless Chromium browser for interactive login.

        Returns:
            Tuple of (Browser, Page) instances.

        Raises:
            RuntimeError: If browser launch fails.
        """
        try:
            p = await async_playwright().start()
            self.browser = await p.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            self.logger.info("Browser launched in non-headless mode")
            return self.browser, self.page
        except Exception as e:
            self.logger.error(f"Failed to launch browser: {e}")
            raise RuntimeError(f"Browser launch failed: {e}") from e

    async def wait_for_successful_login(self, page: Page) -> bool:
        """Wait for successful LinkedIn login and MFA completion.

        Monitors page navigation and checks for authenticated page elements
        to confirm successful login.

        Args:
            page: Playwright Page instance.

        Returns:
            True if login successful (home page detected), False on timeout.
        """
        try:
            # Wait for navigation to home feed (up to 120s)
            await page.wait_for_url("**/feed/**", timeout=self.mfa_timeout)
            self.logger.info("Navigation to home feed detected")
            return True
        except Exception:
            # Fallback: check for authenticated page elements
            try:
                await page.wait_for_selector(
                    "[data-test-id='feed']",
                    timeout=self.mfa_timeout
                )
                self.logger.info("Feed element detected - login successful")
                return True
            except Exception:
                self.logger.warning("Timeout waiting for authenticated state")
                return False

    async def export_session(self) -> bool:
        """Export browser context (cookies, storage) to session.json.

        Captures all authentication data from the live browser session
        for later reuse.

        Returns:
            True if export successful, False otherwise.
        """
        if not self.context or not self.page:
            self.logger.error("No active context/page to export")
            return False

        try:
            # Export storage state (cookies + localStorage + sessionStorage)
            await self.context.storage_state(path=str(self.session_file))

            # Verify file exists and is not empty
            if not self.session_file.exists():
                self.logger.error("Session file not created after export")
                return False

            file_size = self.session_file.stat().st_size
            if file_size == 0:
                self.logger.error("Session file is empty")
                return False

            # Validate JSON structure
            try:
                with open(self.session_file) as f:
                    data = json.load(f)
                    if "cookies" not in data or "origins" not in data:
                        self.logger.error("Session file missing required keys")
                        return False
            except json.JSONDecodeError as e:
                self.logger.error(f"Session file contains invalid JSON: {e}")
                return False

            self.logger.info(f"Session exported successfully to {self.session_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to export session: {e}")
            return False

    async def session_exists(self) -> bool:
        """Check if session.json file exists.

        Returns:
            True if session file exists, False otherwise.
        """
        exists = self.session_file.exists()
        self.logger.debug(f"Session file exists: {exists}")
        return exists

    async def validate_session(self) -> bool:
        """Validate saved session by loading and checking authentication state.

        Loads session into temporary context and navigates to LinkedIn home
        to confirm session is still valid (not expired).

        Returns:
            True if session valid, False if expired or invalid.
        """
        if not await self.session_exists():
            self.logger.warning("No session file to validate")
            return False

        browser = None
        context = None
        try:
            # Load session into temporary context
            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=str(self.session_file))
            page = await context.new_page()

            # Navigate to LinkedIn home
            await page.goto("https://www.linkedin.com/home", timeout=10000)

            # Check for authenticated page elements
            selectors = [
                "[data-test-id='feed']",
                "main.global-nav-container",
                "a[href*='/home']",
                "button[aria-label*='Profile']"
            ]

            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=2000)
                    self.logger.info("Session validated - authenticated element found")
                    return True
                except Exception:
                    continue

            self.logger.warning("Session validation failed - no authenticated elements")
            return False

        except Exception as e:
            self.logger.warning(f"Session validation error: {e}")
            return False
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

    async def load_session(self) -> BrowserContext:
        """Load session from session.json into headless browser context.

        Creates a new headless Playwright context with saved authentication state.

        Returns:
            BrowserContext authenticated with saved session state.

        Raises:
            FileNotFoundError: If session.json does not exist.
            Exception: If context creation fails.
        """
        if not await self.session_exists():
            raise FileNotFoundError(f"Session file not found: {self.session_file}")

        try:
            # Validate JSON structure before loading
            with open(self.session_file) as f:
                data = json.load(f)
                if "cookies" not in data or "origins" not in data:
                    raise ValueError("Session file missing required keys")
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Corrupted session file: {e}")
            self.session_file.unlink()  # Delete corrupted file
            raise FileNotFoundError(f"Session file corrupted and deleted: {e}") from e

        try:
            p = await async_playwright().start()
            self.browser = await p.chromium.launch(headless=True)
            context = await self.browser.new_context(
                storage_state=str(self.session_file)
            )
            self.logger.info("Session loaded into headless context")
            return context
        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")
            raise

    async def interactive_login(self) -> bool:
        """Execute full interactive login flow.

        Launches non-headless browser, navigates to LinkedIn login, waits for
        manual user authentication (including MFA), then exports session state.

        Returns:
            True if login successful and session exported, False otherwise.
        """
        try:
            # Launch non-headless browser
            browser, page = await self.launch_browser_for_login()

            # Navigate to LinkedIn login
            self.logger.info("Navigating to LinkedIn login page...")
            await page.goto("https://www.linkedin.com/login")

            # Prompt user
            print("\n" + "=" * 60)
            print("Launching browser for LinkedIn login...")
            print(f"Please log in manually in the browser window.")
            print(f"MFA will be handled there as needed.")
            print(f"You have {self.mfa_timeout // 1000} seconds to complete login.")
            print("=" * 60 + "\n")

            # Wait for successful login
            if not await self.wait_for_successful_login(page):
                self.logger.error("Login timeout or failed")
                return False

            # Export session
            if not await self.export_session():
                self.logger.error("Failed to export session after login")
                return False

            self.logger.info("Interactive login completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Interactive login failed: {e}")
            return False
        finally:
            await self.cleanup()

    async def get_authenticated_context(self) -> BrowserContext:
        """Get authenticated browser context (load session or prompt login).

        Smart entry point that:
        1. Checks for existing session.json
        2. Validates it if found
        3. Loads it if valid
        4. Prompts interactive login if missing or expired
        5. Returns authenticated context

        Returns:
            BrowserContext authenticated for LinkedIn scraping.

        Raises:
            RuntimeError: If login fails after retries.
        """
        # Try to use existing session
        if await self.session_exists():
            self.logger.info("Found existing session file")
            if await self.validate_session():
                self.logger.info("Session valid - loading...")
                return await self.load_session()
            else:
                self.logger.warning("Session invalid or expired")

        # No session or validation failed - interactive login required
        self.logger.info("Starting interactive login...")
        if await self.interactive_login():
            return await self.load_session()
        else:
            raise RuntimeError("Interactive login failed - unable to authenticate")

    async def cleanup(self):
        """Clean up browser resources.

        Closes page, context, and browser instances.
        """
        try:
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            self.logger.debug("Browser cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup."""
        await self.cleanup()
        return False
