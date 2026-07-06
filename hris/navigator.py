"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : navigator.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Navigator

Sprint 6.14:
- Navigate after manual login
- Open Time Attendance & Overtime menu
- Open Overtime Upload Attendance page
- Mock-compatible for local test

=========================================================
"""

from __future__ import annotations

from playwright.sync_api import Page

from shared.logger import get_logger

logger = get_logger(__name__)


class HRISNavigator:
    """
    HRIS page navigator.

    This class contains browser navigation actions after operator login.
    """

    def __init__(
        self,
        page: Page,
    ) -> None:
        self.page = page

    def open_overtime_upload_attendance(self) -> None:
        """
        Navigate to Overtime Upload Attendance page.
        """
        logger.info(
            "Navigating to Time Attendance & Overtime menu."
        )

        self._click_by_text(
            "Time Attendance & Overtime",
        )

        logger.info(
            "Navigating to Overtime Upload Attendance page."
        )

        self._click_by_text(
            "Overtime Upload Attendance",
        )

        logger.info(
            "Overtime Upload Attendance page opened."
        )

    def _click_by_text(
        self,
        text: str,
    ) -> None:
        """
        Click element by visible text.
        """
        locator = self.page.get_by_text(
            text,
            exact=True,
        )

        locator.wait_for(
            state="visible",
            timeout=10_000,
        )

        locator.click()

    def verify_upload_page_opened(self) -> bool:
        """
        Verify upload page marker exists.

        For mock test:
        - Upload page contains text: Upload Attendance Page

        Later for real HRIS:
        - This can be adjusted based on real page marker.
        """
        marker = self.page.get_by_text(
            "Upload Attendance Page",
            exact=True,
        )

        try:
            marker.wait_for(
                state="visible",
                timeout=5_000,
            )
            return True
        except Exception:
            return False