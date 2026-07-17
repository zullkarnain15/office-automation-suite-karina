"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : engine.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Upload Engine

Sprint 6.11:
- Read HRIS configuration
- Create upload plan
- Create job ID
- Create job artifacts
- Create upload report
- No browser automation yet

=========================================================
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from hris.artifact_writer import HRISJobArtifacts
from hris.artifact_writer import HRISJobArtifactWriter
from hris.job_manager import HRISUploadJobManager
from hris.job_manager import HRISUploadPlan
from hris.report_writer import HRISUploadReportWriter
from shared.config_manager import HRISConfiguration
from shared.config_manager import HRISConfigurationReader
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISUploadEngineResult:
    """
    HRIS Upload Engine result.
    """

    success: bool
    message: str
    job_id: str | None
    workflow: str
    upload_plan: HRISUploadPlan | None
    artifacts: HRISJobArtifacts | None
    report_file: Path | None


class HRISUploadEngine:
    """
    HRIS Upload Engine Orchestrator.

    This class coordinates HRIS preparation steps before browser automation.
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

        self.config_reader = HRISConfigurationReader(
            self.configuration_file,
        )
        self.job_manager = HRISUploadJobManager()
        self.artifact_writer = HRISJobArtifactWriter()
        self.report_writer = HRISUploadReportWriter()
        self._assisted_diagnostic_context: dict[str, object] = {}

    def prepare_upload_job(self) -> HRISUploadEngineResult:
        """
        Prepare HRIS upload job.

        Browser automation must only start after this method returns success=True.
        """
        logger.info(
            "Preparing HRIS upload job. Workflow=%s",
            self.workflow,
        )

        try:
            configuration = self._read_configuration()

            upload_plan = self._create_upload_plan(
                configuration=configuration,
            )

            if not upload_plan.is_valid:
                logger.warning(
                    "HRIS upload pre-validation failed: %s",
                    upload_plan.message,
                )

                return HRISUploadEngineResult(
                    success=False,
                    message=upload_plan.message,
                    job_id=None,
                    workflow=upload_plan.workflow,
                    upload_plan=upload_plan,
                    artifacts=None,
                    report_file=None,
                )

            job_id = self.job_manager.create_job_id(
                upload_plan.workflow,
            )

            artifacts = self.artifact_writer.prepare_job_artifacts(
                output_root=self.output_root,
                workflow=upload_plan.workflow,
                job_id=job_id,
                upload_plan=upload_plan,
            )

            report_file = self.report_writer.write_upload_report(
                artifacts=artifacts,
                upload_plan=upload_plan,
            )

            self.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="HRIS upload job prepared successfully.",
            )

            self.artifact_writer.write_process_log(
                artifacts=artifacts,
                message=f"Upload report created: {report_file.name}",
            )

            logger.info(
                "HRIS upload job prepared successfully. Job ID=%s",
                job_id,
            )

            return HRISUploadEngineResult(
                success=True,
                message="HRIS upload job prepared successfully.",
                job_id=job_id,
                workflow=upload_plan.workflow,
                upload_plan=upload_plan,
                artifacts=artifacts,
                report_file=report_file,
            )

        except Exception as error:
            logger.exception(
                "HRIS upload job preparation failed."
            )

            return HRISUploadEngineResult(
                success=False,
                message=str(error),
                job_id=None,
                workflow=self.workflow,
                upload_plan=None,
                artifacts=None,
                report_file=None,
            )

    def _read_configuration(self) -> HRISConfiguration:
        """
        Read HRIS configuration workbook.
        """
        return self.config_reader.read()

    def _create_upload_plan(
        self,
        configuration: HRISConfiguration,
    ) -> HRISUploadPlan:
        """
        Create HRIS upload plan.
        """
        return self.job_manager.create_upload_plan(
            configuration=configuration,
            txt_folder=self.txt_folder,
            workflow=self.workflow,
        )

@dataclass(slots=True)
class HRISFullUploadEngineResult:
    """
    HRIS Full Upload Engine result.
    """

    success: bool
    message: str
    job_id: str | None
    workflow: str
    report_folder: Path | None
    report_file: Path | None
    summary_json_file: Path | None
    process_log_file: Path | None
    success_count: int
    failed_count: int
    diagnostic_folder: Path | None = None
    diagnostic_zip_file: Path | None = None


class HRISFullUploadEngine:
    """
    HRIS Full Upload Engine.

    This class runs the full HRIS upload flow:
    - Read configuration
    - Create upload plan
    - Create artifacts
    - Create report
    - Open browser
    - Navigate upload page
    - Batch upload TXT files
    - Update summary
    - Move files
    - Update report
    - Close browser
    """

    def __init__(
        self,
        configuration_file: str | Path,
        txt_folder: str | Path,
        output_root: str | Path,
        workflow: str,
        start_date: str,
        end_date: str,
        wait_for_manual_login: bool = True,
        manual_login_callback: Callable[[], None] | None = None,
        manual_checkpoint_callback: Callable[[str], None] | None = None,
        hris_username: str | None = None,
        hris_password: str | None = None,
        close_browser_on_error: bool = True,
        manual_verification_callback: Callable[[str], str] | None = None,
    ) -> None:
        self.configuration_file = Path(configuration_file)
        self.txt_folder = Path(txt_folder)
        self.output_root = Path(output_root)
        self.workflow = workflow
        self.start_date = start_date
        self.end_date = end_date
        self.wait_for_manual_login = wait_for_manual_login
        self.manual_login_callback = manual_login_callback
        self.manual_checkpoint_callback = manual_checkpoint_callback
        self.hris_username = hris_username
        self.hris_password = hris_password
        self.close_browser_on_error = close_browser_on_error
        self.manual_verification_callback = manual_verification_callback

        self.config_reader = HRISConfigurationReader(
            self.configuration_file,
        )
        self.job_manager = HRISUploadJobManager()
        self.artifact_writer = HRISJobArtifactWriter()
        self.report_writer = HRISUploadReportWriter()
        self._assisted_diagnostic_context: dict[str, object] = {}

    def run(self) -> HRISFullUploadEngineResult:
        """
        Run full HRIS upload process.
        """
        from hris.browser import HRISBrowserManager
        from hris.file_manager import HRISFileManager
        from hris.navigator import HRISNavigator

        logger.info(
            "Starting HRIS full upload engine. Workflow=%s",
            self.workflow,
        )

        browser_manager = None
        artifacts = None
        report_file = None
        job_id = None
        configuration = None
        upload_plan = None
        session = None
        diagnostic_folder = None
        close_browser = True

        try:
            configuration = self.config_reader.read()

            upload_plan = self.job_manager.create_upload_plan(
                configuration=configuration,
                txt_folder=self.txt_folder,
                workflow=self.workflow,
            )

            if not upload_plan.is_valid:
                return HRISFullUploadEngineResult(
                    success=False,
                    message=upload_plan.message,
                    job_id=None,
                    workflow=upload_plan.workflow,
                    report_folder=None,
                    report_file=None,
                    summary_json_file=None,
                    process_log_file=None,
                    success_count=0,
                    failed_count=0,
                )

            job_id = self.job_manager.create_job_id(
                upload_plan.workflow,
            )

            artifacts = self.artifact_writer.prepare_job_artifacts(
                output_root=self.output_root,
                workflow=upload_plan.workflow,
                job_id=job_id,
                upload_plan=upload_plan,
            )

            report_file = self.report_writer.write_upload_report(
                artifacts=artifacts,
                upload_plan=upload_plan,
            )

            self.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="HRIS full upload engine started.",
            )

            browser_manager = HRISBrowserManager(
                configuration=configuration,
            )

            session = browser_manager.open_login_page()

            self.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="HRIS browser opened.",
            )

            if self.wait_for_manual_login:
                if self.manual_login_callback is not None:
                    self.manual_login_callback()
                else:
                    browser_manager.wait_for_manual_login()

                session.page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=30_000,
                )

                self.artifact_writer.write_process_log(
                    artifacts=artifacts,
                    message="Operator confirmed manual login.",
                )
            elif self.hris_username and self.hris_password:
                automatic_login_submitted = True

                try:
                    browser_manager.login(
                        username=self.hris_username,
                        password=self.hris_password,
                    )
                except Exception:
                    logger.exception(
                        "Automatic HRIS login failed."
                    )

                    if self.manual_login_callback is None:
                        raise

                    self.artifact_writer.write_process_log(
                        artifacts=artifacts,
                        message=(
                            "Automatic HRIS login failed. "
                            "Waiting for manual login confirmation."
                        ),
                    )

                    self.manual_login_callback()
                    automatic_login_submitted = False

                    session.page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=30_000,
                    )

                login_message = (
                    "Automatic HRIS login submitted."
                    if automatic_login_submitted
                    else "Operator confirmed manual login after automatic login fallback."
                )

                self.artifact_writer.write_process_log(
                    artifacts=artifacts,
                    message=login_message,
                )

            navigator = HRISNavigator(
                page=session.page,
            )

            navigator.open_overtime_upload_attendance()

            self.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="Overtime Upload Attendance page opened.",
            )

            batch_result = self._run_assisted_batch(
                configuration=configuration,
                upload_plan=upload_plan,
                page=session.page,
            )

            self.artifact_writer.update_summary_after_batch(
                artifacts=artifacts,
                batch_result=batch_result,
            )

            file_manager = HRISFileManager()

            move_results = file_manager.move_uploaded_files(
                artifacts=artifacts,
                plan_items=batch_result.results,
            )

            self.artifact_writer.update_summary_after_file_move(
                artifacts=artifacts,
                move_results=move_results,
            )

            summary = self.artifact_writer.read_summary(
                artifacts.summary_json_file,
            )

            self.report_writer.update_report_after_upload(
                report_file=report_file,
                summary=summary,
            )

            if batch_result.failed_count > 0:
                diagnostic_folder = self._write_diagnostic_pack(
                    artifacts=artifacts,
                    configuration=configuration,
                    upload_plan=upload_plan,
                    report_file=report_file,
                    page=session.page,
                    error_message=summary.get(
                        "message",
                        "HRIS batch upload finished with failed item(s).",
                    ),
                    traceback_text=batch_result.error_traceback,
                    stage="batch_upload",
                )

            self.artifact_writer.write_process_log(
                artifacts=artifacts,
                message="HRIS full upload engine finished.",
            )

            return HRISFullUploadEngineResult(
                success=batch_result.failed_count == 0,
                message=summary.get(
                    "message",
                    "HRIS full upload finished.",
                ),
                job_id=job_id,
                workflow=upload_plan.workflow,
                report_folder=artifacts.job_report_folder,
                report_file=report_file,
                summary_json_file=artifacts.summary_json_file,
                process_log_file=artifacts.process_log_file,
                success_count=batch_result.success_count,
                failed_count=batch_result.failed_count,
                diagnostic_folder=diagnostic_folder,
                diagnostic_zip_file=(
                    diagnostic_folder.with_suffix(".zip")
                    if diagnostic_folder is not None
                    else None
                ),
            )

        except Exception as error:
            close_browser = self.close_browser_on_error

            logger.exception(
                "HRIS full upload engine failed."
            )

            error_message = str(error)

            if not close_browser and browser_manager is not None:
                error_message = (
                    f"{error_message} "
                    "Browser kept open for inspection."
                )

            if artifacts is not None:
                self.artifact_writer.write_process_log(
                    artifacts=artifacts,
                    message=f"HRIS full upload engine failed: {error_message}",
                )

                diagnostic_folder = self._write_diagnostic_pack(
                    artifacts=artifacts,
                    configuration=configuration,
                    upload_plan=upload_plan,
                    report_file=report_file,
                    page=session.page if session is not None else None,
                    error_message=error_message,
                    traceback_text=traceback.format_exc(),
                    stage="engine_exception",
                )

            return HRISFullUploadEngineResult(
                success=False,
                message=error_message,
                job_id=job_id,
                workflow=self.workflow,
                report_folder=artifacts.job_report_folder if artifacts else None,
                report_file=report_file,
                summary_json_file=artifacts.summary_json_file if artifacts else None,
                process_log_file=artifacts.process_log_file if artifacts else None,
                success_count=0,
                failed_count=0,
                diagnostic_folder=diagnostic_folder,
                diagnostic_zip_file=(
                    diagnostic_folder.with_suffix(".zip")
                    if diagnostic_folder is not None
                    else None
                ),
            )

        finally:
            if browser_manager is not None and close_browser:
                browser_manager.close()

    def _write_diagnostic_pack(
        self,
        artifacts: HRISJobArtifacts,
        configuration: HRISConfiguration | None,
        upload_plan: HRISUploadPlan | None,
        report_file: str | Path | None,
        page: object | None,
        error_message: str,
        traceback_text: str,
        stage: str,
    ) -> Path:
        """
        Create HRIS diagnostic pack for failed upload.
        """
        from hris.diagnostics import HRISDiagnosticPackWriter

        diagnostic_writer = HRISDiagnosticPackWriter()

        diagnostic_folder = diagnostic_writer.write_diagnostic_pack(
            artifacts=artifacts,
            configuration=configuration,
            upload_plan=upload_plan,
            report_file=report_file,
            page=page,
            error_message=error_message,
            traceback_text=traceback_text,
            stage=stage,
            assisted_context=self._assisted_diagnostic_context,
        )

        self.artifact_writer.write_process_log(
            artifacts=artifacts,
            message=f"Diagnostic pack created: {diagnostic_folder}",
        )

        return diagnostic_folder

    def _run_assisted_batch(
        self,
        configuration: HRISConfiguration,
        upload_plan: HRISUploadPlan,
        page: object,
    ) -> object:
        """Run configured assisted steps while preserving batch result shape."""
        from hris.assisted_replay import HRISAssistedReplayEngine
        from hris.assisted_verifier import HRISAssistedResultVerifier
        from hris.batch_uploader import HRISBatchUploader
        from hris.click_profile import HRISClickProfileManager
        from shared.config_manager import resolve_hris_macro_steps

        post_upload_steps = resolve_hris_macro_steps(
            configuration.assisted_steps
        )

        profile_path = HRISClickProfileManager.resolve_profile_path(configuration)
        if not profile_path.exists():
            raise FileNotFoundError(
                f"HRIS click profile not found: {profile_path}. "
                "Run Calibrate Click Profile first."
            )
        profile = HRISClickProfileManager.load_profile(profile_path)
        self._assisted_diagnostic_context = {
            "profile_path": str(profile_path),
            "profile_validation_result": "NOT CHECKED",
            "assisted_steps": [
                {
                    "sequence": step.sequence,
                    "step_name": step.step_name,
                    "action": step.action,
                    "input_source": step.input_source,
                    "method": step.method,
                    "required": step.required,
                }
                for step in post_upload_steps
            ],
        }

        if self._to_bool(
            configuration.upload.get("Require_Profile_Match", True)
        ):
            import pyautogui

            screen = pyautogui.size()
            validation = HRISClickProfileManager.validate_profile(
                profile,
                (int(screen.width), int(screen.height)),
                configuration.upload,
                current_scale_percent=self._get_display_scale_percent(),
                required_steps=post_upload_steps,
            )
            self._assisted_diagnostic_context[
                "profile_validation_result"
            ] = validation.message
            if not validation.valid:
                raise RuntimeError(
                    f"HRIS click profile validation failed: {validation.message}"
                )

        replay = HRISAssistedReplayEngine(
            configuration=configuration,
            profile=profile,
            page=page,
            manual_recovery_callback=self.manual_checkpoint_callback,
        )
        verifier = HRISAssistedResultVerifier(
            page=page,
            configuration=configuration,
            manual_callback=self.manual_verification_callback,
        )

        def run_post_upload_recorder(
            item: object,
            start_date: str,
            end_date: str,
        ) -> object:
            result = replay.run_item(item, start_date, end_date)
            self._assisted_diagnostic_context.update(replay.last_context)

            if not result.success:
                return result

            verification = verifier.verify_item(item)
            self._assisted_diagnostic_context[
                "verification_status"
            ] = verification.status
            self._assisted_diagnostic_context[
                "verification_message"
            ] = verification.message
            self._record_assisted_verification(item, verification)
            if verification.submitted:
                result.message = verification.message
                return result

            result.success = False
            result.message = verification.message
            return result

        batch_uploader = HRISBatchUploader(
            page=page,
            manual_checkpoint_callback=self.manual_checkpoint_callback,
            post_upload_recorder_callback=run_post_upload_recorder,
        )
        return batch_uploader.upload_batch(
            upload_plan=upload_plan,
            start_date=self.start_date,
            end_date=self.end_date,
            stop_on_first_failure=self._to_bool(
                configuration.upload.get("Stop_On_First_Failure", True)
            ),
        )

    @staticmethod
    def _record_assisted_verification(
        item: object,
        verification: object,
    ) -> None:
        """Persist assisted verification fields used by summary and report."""
        item.verification_status = verification.status
        item.process_instance = verification.process_instance

    @staticmethod
    def _to_bool(value: object) -> bool:
        return str(value).strip().lower() in {"true", "1", "yes", "y"}

    @staticmethod
    def _get_display_scale_percent() -> int:
        try:
            import ctypes
            return round(ctypes.windll.shcore.GetScaleFactorForDevice(0))
        except Exception:
            return 100
