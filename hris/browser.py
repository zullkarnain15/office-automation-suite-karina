"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : browser.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Browser Session

Sprint 6.12:
- Open Microsoft Edge using Playwright
- Open HRIS URL from configuration
- Manual login by operator
- No HRIS navigation yet
- No TXT upload yet

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser
from playwright.sync_api import BrowserContext
from playwright.sync_api import Page
from playwright.sync_api import Playwright
from playwright.sync_api import sync_playwright

from shared.config_manager import HRISConfiguration
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISBrowserSession:
    """
    Active HRIS browser session.
    """

    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page


class HRISBrowserManager:
    """
    HRIS Browser Manager.

    Opens Microsoft Edge and lets operator login manually.
    """

    def __init__(
        self,
        configuration: HRISConfiguration,
    ) -> None:
        self.configuration = configuration
        self._session: HRISBrowserSession | None = None

    def open_login_page(self) -> HRISBrowserSession:
        """
        Open HRIS login page in Microsoft Edge.
        """
        hris_url = self._get_hris_url()
        browser_channel = self._get_browser_channel()
        headless = self._get_headless()
        window_x, window_y, window_width, window_height = (
            self._get_window_geometry()
        )

        logger.info(
            "Opening HRIS login page. URL=%s, Channel=%s, Headless=%s",
            hris_url,
            browser_channel,
            headless,
        )

        playwright = sync_playwright().start()

        browser = playwright.chromium.launch(
            channel=browser_channel,
            headless=headless,
            args=[
                f"--window-position={window_x},{window_y}",
                f"--window-size={window_width},{window_height}",
                "--high-dpi-support=1",
                "--force-device-scale-factor=1",
            ],
        )

        context = browser.new_context(
            accept_downloads=True,
            no_viewport=True,
        )

        page = context.new_page()
        page.goto(
            hris_url,
            wait_until="domcontentloaded",
        )
        self._apply_browser_zoom(page)

        self._session = HRISBrowserSession(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
        )

        logger.info(
            "HRIS login page opened successfully."
        )

        return self._session

    def _get_window_geometry(self) -> tuple[int, int, int, int]:
        """Return configured native Edge window geometry."""
        upload = self.configuration.upload
        return (
            self._to_int(upload.get("Browser_X"), 0),
            self._to_int(upload.get("Browser_Y"), 0),
            self._to_int(upload.get("Browser_Width"), 1200, minimum=640),
            self._to_int(upload.get("Browser_Height"), 800, minimum=480),
        )

    def _apply_browser_zoom(self, page: Page) -> None:
        """Reset Edge page zoom and apply supported configured increments."""
        expected_zoom = self._to_int(
            self.configuration.upload.get("Browser_Zoom"),
            100,
            minimum=25,
        )
        page.keyboard.press("Control+0")

        # Chromium zoom uses discrete steps. Default HRIS profile is 100%.
        direction = "Control+Equal" if expected_zoom > 100 else "Control+-"
        steps = round(abs(expected_zoom - 100) / 25)
        for _ in range(steps):
            page.keyboard.press(direction)

    @staticmethod
    def _to_int(
        value: Any,
        default: int,
        minimum: int | None = None,
    ) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = default
        if minimum is not None:
            result = max(minimum, result)
        return result

    def wait_for_manual_login(
        self,
        message: str | None = None,
    ) -> None:
        """
        Wait for operator confirmation after manual login.

        For this sprint, confirmation is done from terminal.
        Later, GUI will replace this with Continue Upload button.
        """
        if message is None:
            message = (
                "Silakan login HRIS di browser yang terbuka. "
                "Setelah berhasil login, tekan ENTER di terminal ini..."
            )

        print()
        print("=" * 80)
        print(message)
        print("=" * 80)
        input()

        logger.info(
            "Operator confirmed manual HRIS login."
        )

    def login(
        self,
        username: str,
        password: str,
    ) -> None:
        """
        Fill HRIS login form and submit it.
        """
        if self._session is None:
            raise RuntimeError("HRIS browser session is not open.")

        page = self._session.page

        logger.info("Starting automatic HRIS login.")

        username_input = self._find_first_visible_locator(
            [
                "#username",
                "#userName",
                "#userid",
                "#user_id",
                "input[name='username']",
                "input[name='userName']",
                "input[name='userid']",
                "input[name='user_id']",
                "input[type='text']",
            ]
        )

        password_input = self._find_first_visible_locator(
            [
                "#password",
                "#pwd",
                "input[name='password']",
                "input[name='pwd']",
                "input[type='password']",
            ]
        )

        username_input.fill(username)
        password_input.fill(password)

        login_button = self._find_first_visible_locator(
            [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Login')",
                "button:has-text('Log In')",
                "button:has-text('Sign In')",
                "button[name='submit']",
                "[name='submit']",
                "input[value='Login']",
                "input[value='Log In']",
                "input[value='Sign In']",
            ]
        )

        login_button.click()

        page.wait_for_load_state(
            "domcontentloaded",
            timeout=30_000,
        )

        logger.info("Automatic HRIS login submitted.")

    def close(self) -> None:
        """
        Close browser session.
        """
        if self._session is None:
            return

        logger.info(
            "Closing HRIS browser session."
        )

        self._session.context.close()
        self._session.browser.close()
        self._session.playwright.stop()

        self._session = None

    def _get_hris_url(self) -> str:
        """
        Get HRIS URL from configuration.
        """
        value = self.configuration.general.get("HRIS_URL")

        if value is None:
            raise ValueError(
                "HRIS_URL is missing in HRIS configuration."
            )

        hris_url = str(value).strip()

        if not hris_url:
            raise ValueError(
                "HRIS_URL is empty in HRIS configuration."
            )

        return hris_url

    def _get_browser_channel(self) -> str:
        """
        Get Playwright browser channel.

        HRIS v1.0 official browser: Microsoft Edge.
        """
        value = self.configuration.browser.get(
            "Browser_Channel",
            "msedge",
        )

        browser_channel = str(value).strip()

        if not browser_channel:
            return "msedge"

        return browser_channel

    def _get_headless(self) -> bool:
        """
        Get headless setting from configuration.
        """
        value = self.configuration.browser.get(
            "Headless",
            "FALSE",
        )

        value_text = str(value).strip().lower()

        return value_text in (
            "true",
            "1",
            "yes",
            "y",
        )

    def _find_first_visible_locator(
        self,
        selectors: list[str],
    ) -> Any:
        """
        Return the first visible locator from a selector list.
        """
        if self._session is None:
            raise RuntimeError("HRIS browser session is not open.")

        page = self._session.page

        for selector in selectors:
            locator = page.locator(selector).first

            try:
                locator.wait_for(
                    state="visible",
                    timeout=2_000,
                )
                return locator
            except Exception:
                continue

        raise RuntimeError(
            "Required HRIS login element was not found."
        )
