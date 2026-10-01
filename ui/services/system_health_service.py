"""Explicit, zero-write readiness checks for UI3 System Health."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from shared.database import SQLiteConnectionFactory


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    ERROR = "ERROR"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CHECKED = "NOT_CHECKED"


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    code: str
    title: str
    category: str
    status: HealthStatus
    summary: str
    detail: str
    recommendation: str
    checked_at: str


@dataclass(frozen=True, slots=True)
class HealthSummary:
    results: tuple[HealthCheckResult, ...]
    overall: HealthStatus
    checked_at: str | None


class SystemHealthService:
    """Run checks only when explicitly called; results remain in memory."""

    def __init__(self, storage_service) -> None:
        self.storage_service = storage_service
        self.connection_factory = SQLiteConnectionFactory()
        self._last = HealthSummary((), HealthStatus.NOT_CHECKED, None)

    def get_last_result(self) -> tuple[HealthCheckResult, ...]:
        return self._last.results

    def get_summary(self) -> HealthSummary:
        return self._last

    def run_category(self, category: str) -> tuple[HealthCheckResult, ...]:
        return tuple(
            result
            for result in self.run_all_checks()
            if result.category.casefold() == category.casefold()
        )

    def run_all_checks(self) -> tuple[HealthCheckResult, ...]:
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        storage = self.storage_service.resolve_status()
        results = [
            self._database_check(storage, checked_at),
            self._path_check(
                "data_root", "Data Root", "Storage", storage.data_root, checked_at
            ),
            self._registry_check(storage, checked_at),
            self._path_check(
                "backup", "Backup Folder", "Storage", storage.backup_folder, checked_at
            ),
            self._path_check(
                "profiles",
                "Recorder Profile Folder",
                "Storage",
                storage.recorder_profiles_folder,
                checked_at,
            ),
            self._path_check(
                "output", "Output Folder", "Storage", storage.output_folder, checked_at
            ),
            self._path_check(
                "logs", "Logs Folder", "Storage", storage.logs_folder, checked_at
            ),
            self._path_check(
                "diagnostics",
                "Diagnostics Folder",
                "Storage",
                storage.diagnostics_folder,
                checked_at,
            ),
            self._readiness(
                "attendance",
                "Attendance Configuration",
                storage.database_path,
                checked_at,
            ),
            self._readiness(
                "outlook",
                "Outlook Revisi Configuration",
                storage.database_path,
                checked_at,
            ),
            self._readiness(
                "hris", "HRIS Configuration", storage.database_path, checked_at
            ),
            self._readiness(
                "utilities",
                "Utilities Configuration",
                storage.database_path,
                checked_at,
            ),
            self._write_access(storage.data_root, checked_at),
            self._recovery_status(storage.backup_folder, checked_at),
        ]
        overall = self._overall(results)
        self._last = HealthSummary(tuple(results), overall, checked_at)
        return self._last.results

    @staticmethod
    def _result(
        code, title, category, status, summary, checked_at, detail="", recommendation=""
    ):
        return HealthCheckResult(
            code, title, category, status, summary, detail, recommendation, checked_at
        )

    def _database_check(self, storage, checked_at):
        if not storage.database_exists:
            status, summary = HealthStatus.UNAVAILABLE, "Database belum tersedia."
        elif not storage.database_valid:
            status, summary = HealthStatus.ERROR, "Database tidak valid atau rusak."
        else:
            status, summary = HealthStatus.HEALTHY, "Database schema v1 valid."
        return self._result(
            "database",
            "Database",
            "Database",
            status,
            summary,
            checked_at,
            recommendation="Gunakan Settings untuk validasi atau recovery manual.",
        )

    def _path_check(self, code, title, category, path, checked_at):
        if path is None:
            status, summary = HealthStatus.UNAVAILABLE, "Lokasi belum dapat ditentukan."
        elif path.is_dir():
            status, summary = HealthStatus.HEALTHY, f"Tersedia: {path}"
        else:
            status, summary = HealthStatus.WARNING, f"Folder belum tersedia: {path}"
        return self._result(code, title, category, status, summary, checked_at)

    def _registry_check(self, storage, checked_at):
        healthy = storage.registry_status == "Tersedia"
        return self._result(
            "registry",
            "Registry Pointer",
            "Storage",
            HealthStatus.HEALTHY if healthy else HealthStatus.UNAVAILABLE,
            storage.registry_status,
            checked_at,
        )

    def _readiness(self, module, title, database, checked_at):
        if database is None or not database.is_file():
            return self._result(
                module,
                title,
                "Readiness",
                HealthStatus.UNAVAILABLE,
                "Database unavailable.",
                checked_at,
            )
        queries = {
            "attendance": (
                "SELECT (SELECT COUNT(*) FROM attendance_settings) AS settings, "
                "(SELECT COUNT(*) FROM attendance_sources WHERE is_active=1) AS items"
            ),
            "outlook": (
                "SELECT (SELECT COUNT(*) FROM outlook_settings WHERE trim(mailbox_smtp)<>'') AS settings, "
                "((SELECT COUNT(*) FROM outlook_sender_master WHERE is_active=1) + "
                "(SELECT COUNT(*) FROM outlook_subject_rules WHERE is_active=1) + "
                "(SELECT COUNT(*) FROM outlook_reply_templates WHERE is_active=1)) AS items"
            ),
            "hris": (
                "SELECT (SELECT COUNT(*) FROM hris_settings WHERE trim(hris_url)<>'') AS settings, "
                "((SELECT COUNT(*) FROM hris_run_controls WHERE is_active=1) + "
                "(SELECT COUNT(*) FROM hris_assisted_steps WHERE is_active=1)) AS items"
            ),
            "utilities": (
                "SELECT (SELECT COUNT(*) FROM comparison_settings) AS settings, "
                "(SELECT COUNT(*) FROM attachment_consolidation_settings) AS items"
            ),
        }
        try:
            with self.connection_factory.connect(
                database, read_only=True
            ) as connection:
                row = connection.execute(queries[module]).fetchone()
            ready = bool(row["settings"] and row["items"])
            status = HealthStatus.HEALTHY if ready else HealthStatus.NOT_CONFIGURED
            summary = (
                "Konfigurasi dasar tersedia."
                if ready
                else "Konfigurasi dasar belum lengkap."
            )
        except sqlite3.Error as exc:
            status, summary = HealthStatus.ERROR, f"Pemeriksaan gagal: {exc}"
        return self._result(
            module,
            title,
            "Readiness",
            status,
            summary,
            checked_at,
            recommendation="Lengkapi konfigurasi melalui Settings; engine tidak dijalankan.",
        )

    def _write_access(self, root, checked_at):
        if root is None or not root.is_dir():
            status, summary = HealthStatus.UNAVAILABLE, "Data Root belum tersedia."
        else:
            writable = os.access(root, os.W_OK)
            status = HealthStatus.HEALTHY if writable else HealthStatus.ERROR
            summary = (
                "Write access tersedia." if writable else "Write access tidak tersedia."
            )
        return self._result(
            "write_access", "Write Access", "Storage", status, summary, checked_at
        )

    def _recovery_status(self, backup, checked_at):
        available = bool(backup and backup.is_dir())
        return self._result(
            "recovery",
            "Recovery Status",
            "Recovery",
            HealthStatus.HEALTHY if available else HealthStatus.WARNING,
            "Backup folder tersedia." if available else "Backup folder belum tersedia.",
            checked_at,
        )

    @staticmethod
    def _overall(results):
        statuses = {item.status for item in results}
        if HealthStatus.ERROR in statuses:
            return HealthStatus.ERROR
        if HealthStatus.WARNING in statuses or HealthStatus.NOT_CONFIGURED in statuses:
            return HealthStatus.WARNING
        if statuses == {HealthStatus.HEALTHY}:
            return HealthStatus.HEALTHY
        return HealthStatus.UNAVAILABLE
