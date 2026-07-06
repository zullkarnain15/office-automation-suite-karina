"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : uploader.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Upload Page Handler

Sprint 6.15:
- Fill Run Control ID
- Fill start date and end date
- Attach TXT file
- Click Upload
- Confirm OK
- Click Run
- Confirm OK
- Mock-compatible for local test

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator
from playwright.sync_api import Page

from hris.job_manager import HRISUploadPlanItem
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISUploadItemResult:
    """
    Result for one HRIS TXT upload item.
    """

    success: bool
    message: str
    txt_file_name: str
    run_control_id: str


class HRISUploadPageHandler:
    """
    HRIS Upload Page Handler.

    This class handles one TXT upload action on the upload page.
    """

    def __init__(
        self,
        page: Page,
    ) -> None:
        self.page = page

    def upload_one_file(
        self,
        plan_item: HRISUploadPlanItem,
        start_date: str,
        end_date: str,
    ) -> HRISUploadItemResult:
        """
        Upload one TXT file using one Run Control ID.
        """
        logger.info(
            "Uploading TXT file. File=%s, Run Control=%s",
            plan_item.txt_file_name,
            plan_item.run_control_id,
        )

        txt_file_path = Path(plan_item.txt_file_path)

        if not txt_file_path.exists():
            return HRISUploadItemResult(
                success=False,
                message=f"TXT file not found: {txt_file_path}",
                txt_file_name=plan_item.txt_file_name,
                run_control_id=plan_item.run_control_id,
            )

        try:
            self._fill_run_control_id(plan_item.run_control_id)
            self._fill_date_range(
                start_date=start_date,
                end_date=end_date,
            )
            self._attach_txt_file(txt_file_path)
            self._click_upload()
            self._confirm_upload_ok()
            self._click_run()
            self._confirm_run_ok()

            if not self._verify_success():
                return HRISUploadItemResult(
                    success=False,
                    message="Upload success marker was not found.",
                    txt_file_name=plan_item.txt_file_name,
                    run_control_id=plan_item.run_control_id,
                )

            logger.info(
                "TXT upload simulated successfully. File=%s",
                plan_item.txt_file_name,
            )

            return HRISUploadItemResult(
                success=True,
                message="Upload simulated successfully.",
                txt_file_name=plan_item.txt_file_name,
                run_control_id=plan_item.run_control_id,
            )

        except Exception as error:
            logger.exception(
                "TXT upload failed."
            )

            return HRISUploadItemResult(
                success=False,
                message=str(error),
                txt_file_name=plan_item.txt_file_name,
                run_control_id=plan_item.run_control_id,
            )

    def _fill_run_control_id(
        self,
        run_control_id: str,
    ) -> None:
        """
        Fill Run Control ID field.
        """
        field = self.page.locator("#run_control_id")
        field.wait_for(state="visible", timeout=10_000)
        field.fill(run_control_id)

    def _fill_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> None:
        """
        Fill start date and end date fields.
        """
        start_date_field = self.page.locator("#start_date")
        end_date_field = self.page.locator("#end_date")

        start_date_field.wait_for(state="visible", timeout=10_000)
        end_date_field.wait_for(state="visible", timeout=10_000)

        start_date_field.fill(start_date)
        end_date_field.fill(end_date)

    def _attach_txt_file(
        self,
        txt_file_path: Path,
    ) -> None:
        """
        Attach TXT file.
        """
        file_input = self.page.locator("#attachment_file")
        file_input.wait_for(state="attached", timeout=10_000)
        file_input.set_input_files(str(txt_file_path))

    def _click_upload(self) -> None:
        """
        Click Upload button.
        """
        self._click_visible_locator(
            self.page.locator("#upload_button"),
        )

    def _confirm_upload_ok(self) -> None:
        """
        Confirm Upload OK.
        """
        self._click_visible_locator(
            self.page.locator("#upload_ok_button"),
        )

    def _click_run(self) -> None:
        """
        Click Run button.
        """
        self._click_visible_locator(
            self.page.locator("#run_button"),
        )

    def _confirm_run_ok(self) -> None:
        """
        Confirm Run OK.
        """
        self._click_visible_locator(
            self.page.locator("#run_ok_button"),
        )

    def _verify_success(self) -> bool:
        """
        Verify success marker.
        """
        success_marker = self.page.locator("#success_message")

        try:
            success_marker.wait_for(
                state="visible",
                timeout=5_000,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _click_visible_locator(
        locator: Locator,
    ) -> None:
        """
        Wait for a clickable element before clicking it.
        """
        locator.wait_for(
            state="visible",
            timeout=10_000,
        )
        locator.click()
