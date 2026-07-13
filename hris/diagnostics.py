"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : diagnostics.py
Module      : HRIS
Version     : 1.0.0
Python      : 3.14+
=========================================================
HRIS Diagnostic Pack
=========================================================
"""

from __future__ import annotations

import json
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from config.app_config import APP_VERSION
from hris.artifact_writer import HRISJobArtifacts
from hris.job_manager import HRISUploadPlan
from shared.config_manager import HRISConfiguration
from shared.logger import get_logger

logger = get_logger(__name__)

SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "pwd",
    "cookie",
    "session",
    "token",
    "secret",
)


class HRISDiagnosticPackWriter:
    """
    Create safe diagnostic artifacts for failed HRIS uploads.
    """

    def write_diagnostic_pack(
        self,
        artifacts: HRISJobArtifacts,
        configuration: HRISConfiguration | None,
        upload_plan: HRISUploadPlan | None,
        report_file: str | Path | None,
        page: Any | None,
        error_message: str,
        traceback_text: str,
        stage: str,
        assisted_context: dict[str, Any] | None = None,
    ) -> Path:
        """
        Write diagnostic files and return the diagnostic folder path.
        """
        diagnostic_folder = artifacts.job_report_folder / "Diagnostic"
        diagnostic_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._copy_artifact_files(
            diagnostic_folder=diagnostic_folder,
            artifacts=artifacts,
            report_file=report_file,
        )

        self._write_traceback(
            diagnostic_folder=diagnostic_folder,
            traceback_text=traceback_text,
        )

        self._write_browser_state(
            diagnostic_folder=diagnostic_folder,
            page=page,
        )

        self._write_screenshots(
            diagnostic_folder=diagnostic_folder,
            page=page,
        )

        self._write_diagnostic_summary(
            diagnostic_folder=diagnostic_folder,
            artifacts=artifacts,
            configuration=configuration,
            upload_plan=upload_plan,
            report_file=report_file,
            error_message=error_message,
            traceback_text=traceback_text,
            stage=stage,
            assisted_context=assisted_context,
        )

        self._write_zip_file(diagnostic_folder)

        logger.info(
            "HRIS diagnostic pack created: %s",
            diagnostic_folder,
        )

        return diagnostic_folder

    def _copy_artifact_files(
        self,
        diagnostic_folder: Path,
        artifacts: HRISJobArtifacts,
        report_file: str | Path | None,
    ) -> None:
        """
        Copy existing report artifacts into Diagnostic folder.
        """
        files = [
            artifacts.process_log_file,
            artifacts.summary_json_file,
        ]

        if report_file is not None:
            files.append(Path(report_file))

        for file_path in files:
            if file_path.exists():
                shutil.copy2(
                    file_path,
                    diagnostic_folder / file_path.name,
                )

    def _write_traceback(
        self,
        diagnostic_folder: Path,
        traceback_text: str,
    ) -> None:
        """
        Write Python traceback text.
        """
        if not traceback_text:
            traceback_text = "(No Python traceback was captured.)"

        (diagnostic_folder / "exception_traceback.txt").write_text(
            traceback_text,
            encoding="utf-8",
        )

    def _write_browser_state(
        self,
        diagnostic_folder: Path,
        page: Any | None,
    ) -> None:
        """
        Write safe browser state without cookies/session storage.
        """
        lines = [
            "HRIS Browser State",
            "=" * 80,
            f"Captured At : {datetime.now():%Y-%m-%d %H:%M:%S}",
        ]

        if page is None:
            lines.append("Page        : <not available>")
        else:
            lines.append(f"URL         : {self._safe_get_page_url(page)}")
            lines.append(f"Title       : {self._safe_get_page_title(page)}")
            lines.append(f"Frame Count : {self._safe_get_frame_count(page)}")
            lines.append("")
            lines.append("Frame URLs:")

            for frame_url in self._safe_get_frame_urls(page):
                lines.append(f"- {frame_url}")

        (diagnostic_folder / "browser_state.txt").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    def _write_screenshots(
        self,
        diagnostic_folder: Path,
        page: Any | None,
    ) -> None:
        """
        Capture viewport and full-page screenshots.
        """
        if page is None:
            return

        try:
            page.screenshot(
                path=str(diagnostic_folder / "error_screenshot.png"),
                full_page=False,
            )
        except Exception as exc:
            logger.warning("Viewport screenshot failed: %s", exc)

        try:
            page.screenshot(
                path=str(diagnostic_folder / "browser_full_page.png"),
                full_page=True,
            )
        except Exception as exc:
            logger.warning("Full-page screenshot failed: %s", exc)

    def _write_diagnostic_summary(
        self,
        diagnostic_folder: Path,
        artifacts: HRISJobArtifacts,
        configuration: HRISConfiguration | None,
        upload_plan: HRISUploadPlan | None,
        report_file: str | Path | None,
        error_message: str,
        traceback_text: str,
        stage: str,
        assisted_context: dict[str, Any] | None = None,
    ) -> None:
        """
        Write JSON summary with safe diagnostic context.
        """
        summary = {
            "module": "HRIS",
            "app_version": APP_VERSION,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "job": {
                "job_id": artifacts.job_id,
                "workflow": artifacts.workflow,
                "report_folder": str(artifacts.job_report_folder),
                "process_log_file": str(artifacts.process_log_file),
                "summary_json_file": str(artifacts.summary_json_file),
                "report_file": str(report_file) if report_file else "",
            },
            "error": {
                "stage": stage,
                "message": error_message,
                "has_traceback": bool(traceback_text),
            },
            "configuration": self._safe_configuration(configuration),
            "txt_files": self._safe_txt_files(upload_plan),
            "file_status": self._safe_file_status(upload_plan),
            "assisted": self._redact_mapping(assisted_context or {}),
        }

        with (diagnostic_folder / "diagnostic_summary.json").open(
            mode="w",
            encoding="utf-8",
        ) as file:
            json.dump(
                summary,
                file,
                indent=4,
                ensure_ascii=False,
            )

    def _write_zip_file(
        self,
        diagnostic_folder: Path,
    ) -> None:
        """
        Create ZIP archive next to Diagnostic folder.
        """
        zip_base = diagnostic_folder.parent / "Diagnostic"

        shutil.make_archive(
            base_name=str(zip_base),
            format="zip",
            root_dir=diagnostic_folder,
        )

    def _safe_configuration(
        self,
        configuration: HRISConfiguration | None,
    ) -> dict[str, Any]:
        """
        Return configuration details with sensitive fields redacted.
        """
        if configuration is None:
            return {}

        return {
            "configuration_file": str(configuration.configuration_file),
            "general": self._redact_mapping(configuration.general),
            "browser": self._redact_mapping(configuration.browser),
            "upload": self._redact_mapping(configuration.upload),
            "ho_run_control_count": len(configuration.ho_run_controls),
            "branch_run_control_count": len(configuration.branch_run_controls),
            "assisted_steps": [
                {
                    "sequence": step.sequence,
                    "step_name": step.step_name,
                    "action": step.action,
                    "input_source": step.input_source,
                    "method": step.method,
                    "required": step.required,
                }
                for step in configuration.assisted_steps
            ],
        }

    def _redact_mapping(
        self,
        mapping: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Redact sensitive key/value pairs.
        """
        safe_mapping: dict[str, Any] = {}

        for key, value in mapping.items():
            key_text = str(key)
            key_lower = key_text.lower()

            if any(keyword in key_lower for keyword in SENSITIVE_KEYWORDS):
                safe_mapping[key_text] = "<REDACTED>"
            else:
                safe_mapping[key_text] = self._redact_value(value)

        return safe_mapping

    def _redact_value(self, value: Any) -> Any:
        """Preserve safe JSON structure while recursively redacting mappings."""
        if isinstance(value, dict):
            return self._redact_mapping(value)
        if isinstance(value, (list, tuple)):
            return [self._redact_value(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _safe_txt_files(
        self,
        upload_plan: HRISUploadPlan | None,
    ) -> list[dict[str, Any]]:
        """
        Return TXT files planned for upload.
        """
        if upload_plan is None:
            return []

        return [
            {
                "sequence": item.sequence,
                "txt_file_name": item.txt_file_name,
                "txt_file_path": str(item.txt_file_path),
                "run_control_id": item.run_control_id,
            }
            for item in upload_plan.plan_items
        ]

    def _safe_file_status(
        self,
        upload_plan: HRISUploadPlan | None,
    ) -> list[dict[str, Any]]:
        """
        Return per-file upload status.
        """
        if upload_plan is None:
            return []

        return [
            {
                "sequence": item.sequence,
                "txt_file_name": item.txt_file_name,
                "run_control_id": item.run_control_id,
                "status": item.status,
                "message": item.message,
            }
            for item in upload_plan.plan_items
        ]

    @staticmethod
    def _safe_get_page_url(page: Any) -> str:
        try:
            return str(page.url)
        except Exception:
            return "<not available>"

    @staticmethod
    def _safe_get_page_title(page: Any) -> str:
        try:
            return str(page.title())
        except Exception:
            return "<not available>"

    @staticmethod
    def _safe_get_frame_count(page: Any) -> int | str:
        try:
            return len(page.frames)
        except Exception:
            return "<not available>"

    @staticmethod
    def _safe_get_frame_urls(page: Any) -> list[str]:
        try:
            return [
                str(frame.url)
                for frame in page.frames
            ]
        except Exception:
            return []
