"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : session_engine.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Upload Session Engine

Sprint 6.13:
- Prepare HRIS upload job
- Open Microsoft Edge after pre-validation passed
- Let operator login manually
- Write process log
- No menu navigation yet
- No TXT upload yet

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hris.browser import HRISBrowserManager
from hris.engine import HRISUploadEngine
from shared.config_manager import HRISConfigurationReader
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISUploadSessionResult:
    """
    HRIS upload session result.
    """

    success: bool
    message: str
    job_id: str | None
    browser_opened: bool
    login_confirmed: bool
    report_folder: Path | None


class HRISUploadSessionEngine:
    """
    HRIS Upload Session Engine.

    This class integrates upload job preparation with browser session.
    """

    def __init__(
        self,
        configuration_file: str | Path,
        txt_folder: str | Path,
        output_root: str | Path,
        workflow: str,
    ) -> None:
        self.configuration_file = Path(configuration_file)
        self.txt_folder = Path(txt_folder)
        self.output_root = Path(output_root)
        self.workflow = workflow

    def prepare_and_open_login(
        self,
    ) -> HRISUploadSessionResult:
        """
        Prepare upload job and open HRIS login page.

        Browser only opens if pre-validation is successful.
        """
        logger.info(
            "Starting HRIS upload session preparation. Workflow=%s",
            self.workflow,
        )

        upload_engine = HRISUploadEngine(
            configuration_file=self.configuration_file,
            txt_folder=self.txt_folder,
            output_root=self.output_root,
            workflow=self.workflow,
        )

        engine_result = upload_engine.prepare_upload_job()

        if not engine_result.success:
            logger.warning(
                "HRIS upload session stopped before browser opens: %s",
                engine_result.message,
            )

            return HRISUploadSessionResult(
                success=False,
                message=engine_result.message,
                job_id=engine_result.job_id,
                browser_opened=False,
                login_confirmed=False,
                report_folder=None,
            )

        if engine_result.artifacts is None:
            return HRISUploadSessionResult(
                success=False,
                message="HRIS job artifacts are missing.",
                job_id=engine_result.job_id,
                browser_opened=False,
                login_confirmed=False,
                report_folder=None,
            )

        artifacts = engine_result.artifacts

        upload_engine.artifact_writer.write_process_log(
            artifacts=artifacts,
            message="Opening HRIS browser session.",
        )

        reader = HRISConfigurationReader(
            self.configuration_file,
        )
        configuration = reader.read()

        browser_manager = HRISBrowserManager(
            configuration=configuration,
        )

        browser_opened = False
        login_confirmed = False

        try:
            browser_manager.open_login_page()
            browser_opened = True

            upload_engine.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="HRIS login page opened. Waiting for operator manual login.",
            )

            browser_manager.wait_for_manual_login()

            login_confirmed = True

            upload_engine.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="Operator confirmed manual HRIS login.",
            )

            return HRISUploadSessionResult(
                success=True,
                message="HRIS browser session completed successfully.",
                job_id=engine_result.job_id,
                browser_opened=browser_opened,
                login_confirmed=login_confirmed,
                report_folder=artifacts.job_report_folder,
            )

        except Exception as error:
            logger.exception(
                "HRIS browser session failed."
            )

            upload_engine.artifact_writer.write_process_log(
                artifacts=artifacts,
                message=f"HRIS browser session failed: {error}",
            )

            return HRISUploadSessionResult(
                success=False,
                message=str(error),
                job_id=engine_result.job_id,
                browser_opened=browser_opened,
                login_confirmed=login_confirmed,
                report_folder=artifacts.job_report_folder,
            )

        finally:
            browser_manager.close()

            upload_engine.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="HRIS browser session closed.",
            )