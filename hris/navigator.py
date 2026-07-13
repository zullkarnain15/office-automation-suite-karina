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

    def prepare_next_upload(self) -> None:
        """Click the upload menu again before processing the next batch item."""
        logger.info(
            "Clicking Overtime Upload Attendance for the next batch item."
        )
        self._click_overtime_upload_attendance_link()

        if not self.verify_run_control_search_opened():
            raise RuntimeError(
                "Overtime Upload Attendance was clicked, but the Run Control "
                "search page did not open."
            )

        logger.info("Run Control search opened for the next batch item.")

    def _click_overtime_upload_attendance_link(self) -> None:
        """Click the sidebar link, excluding the identical page-title text."""
        last_error: Exception | None = None

        for scope in self._locator_scopes():
            locator = scope.get_by_role(
                "link",
                name="Overtime Upload Attendance",
                exact=True,
            )
            try:
                count = locator.count()
            except Exception as error:
                last_error = error
                continue

            for index in range(count):
                candidate = locator.nth(index)
                try:
                    candidate.wait_for(state="visible", timeout=1_000)
                    candidate.click()
                    self._wait_after_navigation_action()
                    return
                except Exception as error:
                    last_error = error

        raise RuntimeError(
            "Overtime Upload Attendance sidebar link was not found: "
            f"{last_error}"
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

    def verify_run_control_search_opened(self) -> bool:
        """Return True only for the search page, never the upload detail page."""
        selectors = [
            "#PRCSRUNCNTL_RUN_CNTL_ID",
            "[name='PRCSRUNCNTL_RUN_CNTL_ID']",
            "input[id*='RUN_CNTL_ID']",
            "input[name*='RUN_CNTL_ID']",
        ]

        for selector in selectors:
            for scope in self._locator_scopes():
                locator = scope.locator(selector).first
                try:
                    locator.wait_for(state="visible", timeout=750)
                    return True
                except Exception:
                    continue

        return False

    def _locator_scopes(self) -> list[object]:
        """Return the top-level page and all PeopleSoft frame scopes."""
        return [self.page, *getattr(self.page, "frames", [])]

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
