"""Thin adapter for the frozen legacy Attendance reader and engine."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from attendance.engine import AttendanceProcessEngine
from shared.config_manager import AttendanceConfigurationReader
from shared.database.exporting import export_attendance_legacy
from shared.hris_txt_staging import stage_hris_txt_files
from ui.attendance_models import (
    AttendanceCancellationToken,
    AttendanceLogEvent,
    AttendanceOutputFile,
    AttendanceProgressEvent,
    AttendanceResolvedRequest,
    AttendanceRunResult,
    AttendanceSourceValidation,
    AttendanceValidationResult,
)

ProgressCallback = Callable[[AttendanceProgressEvent], None]
LogCallback = Callable[[AttendanceLogEvent], None]


class AttendanceAdapter:
    def __init__(
        self,
        reader_class=AttendanceConfigurationReader,
        engine_class=AttendanceProcessEngine,
    ) -> None:
        self.reader_class = reader_class
        self.engine_class = engine_class

    def validate_configuration(
        self,
        request: AttendanceResolvedRequest,
    ) -> AttendanceValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            with self._configuration_path(request) as path:
                configuration = self.reader_class(path).read()
            sources = (
                configuration.ho_mdb_list
                if request.workflow == "HO"
                else configuration.branch_mdb_list
            )
            details = tuple(
                AttendanceSourceValidation(
                    item.description or item.code,
                    Path(item.mdb_path),
                    True,
                    Path(item.mdb_path).is_file(),
                    os.access(item.mdb_path, os.R_OK),
                    "READY"
                    if Path(item.mdb_path).is_file()
                    and os.access(item.mdb_path, os.R_OK)
                    else "MISSING",
                )
                for item in sources
            )
            if not details:
                errors.append(f"Tidak ada MDB aktif untuk workflow {request.workflow}.")
            missing = sum(not item.exists or not item.readable for item in details)
            if missing:
                errors.append(f"{missing} MDB aktif tidak tersedia/readable.")
            return self._validation(request, details, errors, warnings)
        except Exception as exc:
            errors.append(f"Configuration tidak valid: {exc}")
            return self._validation(request, (), errors, warnings)

    def run(
        self,
        request: AttendanceResolvedRequest,
        *,
        cancellation: AttendanceCancellationToken,
        progress: ProgressCallback,
        log: LogCallback,
    ) -> AttendanceRunResult:
        started = self._now()
        if cancellation.requested:
            return self._cancelled(
                request, started, "Dibatalkan sebelum loading configuration."
            )
        progress(
            AttendanceProgressEvent("LOADING_CONFIGURATION", "Loading Configuration")
        )
        try:
            with self._configuration_path(request) as configuration_path:
                log(
                    self._log(
                        "INFO",
                        f"Reading {request.configuration_source} configuration.",
                    )
                )
                configuration = self.reader_class(configuration_path).read()
                if cancellation.requested:
                    return self._cancelled(
                        request, started, "Dibatalkan setelah loading configuration."
                    )
                progress(
                    AttendanceProgressEvent(
                        "RUNNING_ENGINE",
                        "Reading MDB, pairing, validating, and writing outputs",
                    )
                )
                log(
                    self._log(
                        "INFO", f"Running Attendance engine for {request.workflow}."
                    )
                )
                engine_result = self.engine_class().run(
                    configuration=configuration,
                    output_root=request.output_root,
                    workflow=request.workflow,
                    date_from=datetime.strptime(request.period_start, "%Y-%m-%d"),
                    date_to=datetime.strptime(request.period_end, "%Y-%m-%d"),
                    generate_txt=request.generate_txt,
                    generate_report=request.generate_report,
                )
            outputs = self._outputs(engine_result)
            cancelled = cancellation.requested
            staging_warnings = 0
            if not cancelled:
                staging_warnings = self._stage_hris_txt(request, outputs, log)
            log(
                self._log(
                    "WARNING" if cancelled else "INFO",
                    "Engine stage finished; cancellation applied at safe checkpoint."
                    if cancelled
                    else "Attendance engine completed.",
                )
            )
            progress(AttendanceProgressEvent("FINALIZING", "Finalizing"))
            artifacts = engine_result.get("artifact_result") or {}
            return AttendanceRunResult(
                success=not cancelled,
                cancelled=cancelled,
                job_id=request.job_id,
                workflow=request.workflow,
                started_at=started,
                ended_at=self._now(),
                output_root=request.output_root,
                job_folder=self._existing_path(artifacts.get("artifact_folder")),
                output_files=outputs,
                record_counts={
                    "raw": int(engine_result.get("raw_log_count", 0)),
                    "paired": int(engine_result.get("paired_record_count", 0)),
                    "valid": int(engine_result.get("valid_record_count", 0)),
                    "anomaly": int(engine_result.get("anomaly_record_count", 0)),
                    "duplicate_removed": int(
                        engine_result.get("duplicate_removed_count", 0)
                    ),
                },
                warning_count=sum(
                    1
                    for item in engine_result.get("mdb_summary", ())
                    if item.get("status") != "SUCCESS"
                )
                + int(cancelled)
                + staging_warnings,
                error_summary="Pembatalan diterapkan setelah tahap engine; partial output dipertahankan."
                if cancelled
                else None,
                process_log_path=self._existing_path(artifacts.get("process_log")),
                summary_json_path=self._existing_path(artifacts.get("summary_json")),
            )
        except Exception as exc:
            log(self._log("ERROR", f"Attendance run failed: {exc}"))
            return AttendanceRunResult(
                False,
                False,
                request.job_id,
                request.workflow,
                started,
                self._now(),
                request.output_root,
                None,
                (),
                {},
                error_summary=str(exc),
            )

    @staticmethod
    def _validation(request, sources, errors, warnings):
        return AttendanceValidationResult(
            not errors,
            not errors,
            request.workflow,
            len(sources),
            request.period_start,
            request.period_end,
            request.output_root,
            request.generate_txt,
            request.generate_report,
            tuple(sources),
            tuple(warnings),
            tuple(errors),
        )

    @classmethod
    def _outputs(cls, result) -> tuple[AttendanceOutputFile, ...]:
        candidates: list[tuple[str, object]] = []
        txt = result.get("txt_result") or {}
        candidates.extend(
            ("HRIS_TXT", item.get("file_path"))
            for item in txt.get("generated_files", ())
        )
        report = result.get("report_result") or {}
        candidates.append(("EXCEL_REPORT", report.get("report_file")))
        artifacts = result.get("artifact_result") or {}
        candidates.extend(
            (
                ("OUTPUT_FOLDER", artifacts.get("artifact_folder")),
                ("PROCESS_LOG", artifacts.get("process_log")),
                ("SUMMARY_JSON", artifacts.get("summary_json")),
            )
        )
        return tuple(
            AttendanceOutputFile(role, path)
            for role, value in candidates
            if (path := cls._existing_path(value)) is not None
        )

    @classmethod
    def _stage_hris_txt(cls, request, outputs, log) -> int:
        txt_files = tuple(
            item.path for item in outputs if item.file_type == "HRIS_TXT"
        )
        if not txt_files:
            return 0
        try:
            staged = stage_hris_txt_files(
                txt_files,
                request.output_root,
                request.workflow,
            )
        except Exception as exc:
            log(cls._log("ERROR", f"HRIS staging gagal: {exc}"))
            return 1
        copied = sum(item.status != "SKIPPED_IDENTICAL" for item in staged)
        skipped = len(staged) - copied
        log(
            cls._log(
                "INFO",
                f"HRIS staging selesai: {copied} TXT disalin, "
                f"{skipped} duplikat identik dilewati.",
            )
        )
        return 0

    @staticmethod
    def _existing_path(value) -> Path | None:
        path = Path(str(value)) if value else None
        return path if path is not None and path.exists() else None

    @staticmethod
    @contextmanager
    def _configuration_path(request):
        if request.configuration_path is not None:
            path = request.configuration_path
            if path.suffix.casefold() != ".xlsx" or not path.is_file():
                raise ValueError("Attendance Configuration .xlsx tidak ditemukan.")
            yield path
            return
        if request.database_path is None:
            raise RuntimeError("Database konfigurasi aktif tidak tersedia.")
        with tempfile.TemporaryDirectory(prefix="oask-attendance-config-") as temp:
            path = Path(temp) / "Attendance_Configuration.xlsx"
            export_attendance_legacy(
                request.database_path,
                path,
                overwrite=False,
                create_parent=False,
            )
            yield path

    @classmethod
    def _cancelled(cls, request, started, message):
        return AttendanceRunResult(
            False,
            True,
            request.job_id,
            request.workflow,
            started,
            cls._now(),
            request.output_root,
            None,
            (),
            {},
            warning_count=1,
            error_summary=message,
        )

    @classmethod
    def _log(cls, level: str, message: str) -> AttendanceLogEvent:
        return AttendanceLogEvent(cls._now(), level, message)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
