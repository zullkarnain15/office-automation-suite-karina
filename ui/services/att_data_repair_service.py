"""UI orchestration for Att Data Repair."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date
from pathlib import Path

from shared.database.time_utils import current_timestamp
from ui.services.comparison_result_service import ComparisonResultService
from ui.services.utilities_service import UtilitiesService
from ui.utilities_models import (
    AttDataRepairLogEvent,
    AttDataRepairResolvedRequest,
    AttDataRepairRunResult,
)
from utilities.att_data_repair.configuration import AttDataRepairConfigurationService
from utilities.att_data_repair.job_audit import AttDataRepairJobAudit
from utilities.att_data_repair.report_discovery import AttDataRepairReportDiscovery


class AttDataRepairService:
    """Resolve UI input, run the core engine, and record history."""

    def __init__(
        self,
        storage_service,
        adapter,
        *,
        configuration_service: AttDataRepairConfigurationService | None = None,
        audit: AttDataRepairJobAudit | None = None,
        discovery: AttDataRepairReportDiscovery | None = None,
        factory=None,
    ) -> None:
        self.defaults = UtilitiesService(storage_service, factory)
        self.adapter = adapter
        self.configuration_service = (
            configuration_service or AttDataRepairConfigurationService(factory)
        )
        self.audit = audit or AttDataRepairJobAudit(factory)
        self.discovery = discovery or AttDataRepairReportDiscovery()

    def load_defaults(self):
        return self.defaults.load_defaults()

    def resolve_request(self, request) -> AttDataRepairResolvedRequest:
        defaults = self.load_defaults()
        if not defaults.database_available or defaults.database_path is None:
            raise RuntimeError(defaults.warning)
        try:
            settings = self.configuration_service.read_settings(defaults.database_path)
        except Exception as exc:
            raise RuntimeError(
                "Konfigurasi Att Data Repair tidak dapat dibaca. "
                "Periksa Settings atau database aktif."
            ) from exc
        if not settings.enabled:
            raise ValueError(
                "Att Data Repair sedang dinonaktifkan pada konfigurasi aktif."
            )
        source, source_folder, discovery_result = self._resolve_source(request)

        start, end = self._resolve_period(
            request.use_global_period,
            defaults.period_start,
            defaults.period_end,
            request.period_start,
            request.period_end,
        )
        output = self._resolve_output(
            request.use_global_output,
            defaults.output_root,
            request.output_root,
        )
        if not request.generate_txt and not request.generate_excel_report:
            raise ValueError(
                "Aktifkan minimal salah satu output: TXT atau Excel Report."
            )
        self._output(output)
        job_settings = replace(
            settings,
            generate_txt=request.generate_txt,
            generate_excel_report=request.generate_excel_report,
        )
        self.configuration_service.validate_settings(job_settings)
        return AttDataRepairResolvedRequest(
            ComparisonResultService._job_id(),
            defaults.database_path,
            source,
            start.isoformat(),
            end.isoformat(),
            output,
            request.use_global_period,
            request.use_global_output,
            request.generate_txt,
            request.generate_excel_report,
            job_settings,
            source_folder,
            discovery_result,
        )

    def _resolve_source(self, request) -> tuple[Path, Path | None, object | None]:
        source = request.source_report
        source_folder = getattr(request, "source_report_folder", None)
        if source is not None and str(source).strip():
            source = Path(source)
            if source.is_dir():
                source_folder = source
                source = None
        if source_folder is not None and str(source_folder).strip():
            folder = Path(source_folder)
            if not folder.is_dir():
                raise ValueError("Folder source report tidak ditemukan.")
            result = self.discovery.discover(
                folder,
                recursive=getattr(request, "scan_recursive", True),
            )
            valid_reports = result.valid_candidates
            if not valid_reports:
                raise ValueError(
                    "Tidak ada Excel Report Attachment Consolidation yang valid "
                    "di folder source report."
                )
            if len(valid_reports) > 1:
                raise ValueError(
                    "Folder source report memiliki lebih dari satu Excel Report "
                    "valid. Pilih file report langsung atau gunakan folder yang "
                    "lebih spesifik."
                )
            return valid_reports[0].path, folder, result

        if source is None or not str(source).strip():
            raise ValueError(
                "Pilih Excel Report atau folder hasil Attachment Consolidation terlebih dahulu."
            )
        source = Path(source)
        if source.suffix.casefold() != ".xlsx":
            raise ValueError("File sumber harus berformat .xlsx.")
        if not source.is_file():
            raise ValueError("File sumber tidak ditemukan. Periksa kembali lokasi file.")
        return source, None, None

    def preflight(self, request, *, cancellation):
        resolved = self.resolve_request(request)
        return resolved, self.adapter.validate(resolved, cancellation)

    def run_job(self, resolved, validation, *, cancellation, progress, log):
        if cancellation.requested:
            now = current_timestamp()
            return AttDataRepairRunResult(
                False,
                True,
                resolved.job_id,
                now,
                now,
                None,
                (),
                status="CANCELLED",
                error_summary="Job dibatalkan sebelum engine dimulai.",
            )
        job_request = self.configuration_service.build_job_request(
            settings=resolved.settings,
            source_report=resolved.source_report,
            period_start=date.fromisoformat(resolved.period_start),
            period_end=date.fromisoformat(resolved.period_end),
            output_root=resolved.output_root,
        )
        ui_result, core_result = self.adapter.run(
            resolved,
            job_request,
            cancellation=cancellation,
            progress=progress,
            log=log,
        )
        if core_result is not None:
            recorded = self.audit.safe_record(
                resolved.database_path,
                job_request,
                core_result,
            )
            if recorded:
                log(
                    AttDataRepairLogEvent(
                        current_timestamp(),
                        "INFO",
                        "HISTORY",
                        "History recorded.",
                    )
                )
            else:
                log(
                    AttDataRepairLogEvent(
                        current_timestamp(),
                        "WARNING",
                        "HISTORY",
                        "History gagal dicatat; output tetap dipertahankan.",
                    )
                )
                ui_result = replace(
                    ui_result,
                    warning_count=ui_result.warning_count + 1,
                )
        return ui_result

    def request_cancellation(self, resolved, token) -> None:
        token.request()

    @staticmethod
    def _resolve_period(
        use_global: bool,
        global_start,
        global_end,
        local_start,
        local_end,
    ) -> tuple[date, date]:
        start = global_start if use_global else local_start
        end = global_end if use_global else local_end
        if not start or not end:
            if use_global:
                raise ValueError(
                    "Periode pada General Settings belum lengkap. "
                    "Lengkapi Settings atau gunakan periode lokal."
                )
            raise ValueError("Period Start dan Period End wajib diisi.")
        try:
            first = date.fromisoformat(str(start))
            last = date.fromisoformat(str(end))
        except ValueError as exc:
            raise ValueError("Tanggal harus memakai format YYYY-MM-DD.") from exc
        if first > last:
            raise ValueError("Tanggal mulai tidak boleh lebih besar dari tanggal selesai.")
        return first, last

    @staticmethod
    def _resolve_output(
        use_global: bool,
        global_output: Path | None,
        local_output: Path | None,
    ) -> Path:
        output = global_output if use_global else local_output
        if output is None or not str(output).strip():
            if use_global:
                raise ValueError(
                    "Output Root pada General Settings belum tersedia. "
                    "Lengkapi Settings atau gunakan folder lokal."
                )
            raise ValueError("Pilih folder output terlebih dahulu.")
        return Path(output)

    @staticmethod
    def _output(output: Path) -> None:
        parent = output
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK):
            raise ValueError("Parent Output Root tidak writable.")
