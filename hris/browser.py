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
        )

        context = browser.new_context(
            accept_downloads=True,
        )

        page = context.new_page()
        page.goto(
            hris_url,
            wait_until="domcontentloaded",
        )

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