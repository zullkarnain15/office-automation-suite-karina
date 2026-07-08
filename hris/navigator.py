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

OVERTIME_UPLOAD_COMPONENT_PATH = (
    "/psp/HPROD/EMPLOYEE/HRMS/c/IDOT_ATTENDANCE.IDOT_UPLOAD_ATT.GBL"
)


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

        self._wait_after_navigation_action()

        if not self.verify_upload_page_opened():
            self._open_overtime_upload_attendance_url()

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

        self._wait_after_navigation_action()

    def verify_upload_page_opened(self) -> bool:
        """
        Verify upload page marker exists.

        For mock test:
        - Upload page contains text: Upload Attendance Page

        Later for real HRIS:
        - This can be adjusted based on real page marker.
        """
        markers = [
            self.page.locator("#PRCSRUNCNTL_RUN_CNTL_ID"),
            self.page.locator("#IDOT_UPLOAD_ATT_START_DATE"),
            self.page.locator("#IDOT_UPLOAD_ATT_ATTACHADD"),
            self.page.get_by_text(
                "Upload Attendance Page",
                exact=True,
            ),
        ]

        for marker in markers:
            try:
                marker.first.wait_for(
                    state="visible",
                    timeout=1_500,
                )
                return True
            except Exception:
                continue

        return False

    def _open_overtime_upload_attendance_url(self) -> None:
        """
        Open PeopleSoft Overtime Upload Attendance component directly.
        """
        current_url = self.page.url

        if not current_url.startswith(("http://", "https://")):
            return

        origin = self.page.evaluate("() => window.location.origin")
        target_url = f"{origin}{OVERTIME_UPLOAD_COMPONENT_PATH}"

        logger.info(
            "Opening Overtime Upload Attendance component URL directly: %s",
            target_url,
        )

        self.page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        self._wait_after_navigation_action()

    def _wait_after_navigation_action(self) -> None:
        """
        Wait briefly after a PeopleSoft navigation action.
        """
        try:
            self.page.wait_for_load_state(
                "domcontentloaded",
                timeout=10_000,
            )
        except Exception:
            pass
