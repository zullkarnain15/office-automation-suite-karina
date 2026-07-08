"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : batch_uploader.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Batch Uploader

Sprint 6.16:
- Upload multiple TXT files sequentially
- Use one Run Control ID per TXT file
- Mock-compatible for local test
- No file moving yet
- No report update yet

=========================================================
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import Page

from hris.job_manager import HRISUploadPlan
from hris.job_manager import HRISUploadPlanItem
from hris.job_manager import FILE_STATUS_FAILED
from hris.job_manager import FILE_STATUS_SUCCESS
from hris.navigator import HRISNavigator
from hris.uploader import HRISUploadPageHandler
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISBatchUploadResult:
    """
    HRIS batch upload result.
    """

    total_items: int
    success_count: int
    failed_count: int
    results: list[HRISUploadPlanItem]
    error_traceback: str = ""


class HRISBatchUploader:
    """
    HRIS Batch Uploader.

    Uploads TXT files one by one using prepared upload plan.
    """

    def __init__(
        self,
        page: Page,
        manual_checkpoint_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.page = page
        self.manual_checkpoint_callback = manual_checkpoint_callback
        self.page_handler = HRISUploadPageHandler(
            page=self.page,
            manual_checkpoint_callback=self.manual_checkpoint_callback,
        )
        self.navigator = HRISNavigator(
            page=self.page,
        )

    def upload_batch(
        self,
        upload_plan: HRISUploadPlan,
        start_date: str,
        end_date: str,
        stop_on_first_failure: bool = True,
    ) -> HRISBatchUploadResult:
        """
        Upload all TXT files from upload plan sequentially.
        """
        success_count = 0
        failed_count = 0
        error_traceback = ""

        logger.info(
            "Starting HRIS batch upload. Total item=%s",
            len(upload_plan.plan_items),
        )

        for index, plan_item in enumerate(upload_plan.plan_items):
            if index > 0:
                logger.info(
                    "Reopening Overtime Upload Attendance page before next item."
                )
                self.navigator.open_overtime_upload_attendance()

            result = self.page_handler.upload_one_file(
                plan_item=plan_item,
                start_date=start_date,
                end_date=end_date,
            )

            if result.success:
                plan_item.status = FILE_STATUS_SUCCESS
                plan_item.message = result.message
                success_count += 1

                logger.info(
                    "Batch upload item success. File=%s",
                    plan_item.txt_file_name,
                )
            else:
                plan_item.status = FILE_STATUS_FAILED
                plan_item.message = result.message
                failed_count += 1
                error_traceback = result.traceback_text

                logger.warning(
                    "Batch upload item failed. File=%s, Message=%s",
                    plan_item.txt_file_name,
                    result.message,
                )

                if stop_on_first_failure:
                    break

        logger.info(
            "HRIS batch upload finished. Success=%s, Failed=%s",
            success_count,
            failed_count,
        )

        return HRISBatchUploadResult(
            total_items=len(upload_plan.plan_items),
            success_count=success_count,
            failed_count=failed_count,
            results=upload_plan.plan_items,
            error_traceback=error_traceback,
        )
