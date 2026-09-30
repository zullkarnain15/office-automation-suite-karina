"""Transactional, batched import orchestration for Attendance & OT sources."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from shared.attendance_ot.models import (
    ParsedSourceRow,
    RefreshProgress,
    RefreshFileSummary,
    RefreshPlan,
    RefreshResult,
    ScanIssue,
    SourceCandidate,
    SourceRegistryItem,
    SourceStatus,
    SourceType,
    ScheduleSubtype,
)
from shared.attendance_ot.readers import (
    date_text,
    identifier_text,
    iter_source_rows,
    numeric_value,
    period_date_text,
    text_value,
    time_text,
)
from shared.attendance_ot.scanner import scan_source_folder
from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.time_utils import current_timestamp

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[RefreshProgress], None]


class AttendanceOTImportService:
    def __init__(
        self,
        storage_service,
        database_settings_service,
        *,
        batch_size: int = 1_000,
        factory: SQLiteConnectionFactory | None = None,
        enrichment_service=None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        self.storage_service = storage_service
        self.database_settings_service = database_settings_service
        self.batch_size = batch_size
        self.factory = factory or SQLiteConnectionFactory()
        if enrichment_service is None:
            from shared.attendance_ot.enrichment import AttendanceOTEnrichmentService

            enrichment_service = AttendanceOTEnrichmentService(
                batch_size=batch_size, factory=self.factory
            )
        self.enrichment_service = enrichment_service

    def prepare_refresh(self) -> RefreshPlan:
        analytics_status = self.storage_service.initialize()
        if analytics_status.database_path is None:
            raise RuntimeError("Database analytics belum tersedia.")
        candidates, scan_issues, scanned_types, folder_errors = self._scan_sources()
        existing = {
            self._path_key(item.source_path): item for item in self.list_sources()
        }
        files: list[RefreshFileSummary] = []
        seen_paths = {self._path_key(item.path) for item in candidates}
        seen_paths.update(self._path_key(item.path) for item in scan_issues)
        for candidate in candidates:
            status = self._classify(
                candidate, existing.get(self._path_key(candidate.path))
            )
            files.append(
                RefreshFileSummary(
                    candidate.filename,
                    candidate.source_type.value,
                    status.value,
                    candidate.path,
                )
            )
        for issue in scan_issues:
            files.append(
                RefreshFileSummary(
                    issue.filename,
                    issue.source_type.value,
                    SourceStatus.ERROR.value,
                    issue.path,
                )
            )
        scanned_values = {value.value for value in scanned_types}
        for item in existing.values():
            if (
                item.source_type in scanned_values
                and self._path_key(item.source_path) not in seen_paths
            ):
                files.append(
                    RefreshFileSummary(
                        item.filename,
                        item.source_type,
                        SourceStatus.MISSING.value,
                        item.source_path,
                    )
                )
        files.sort(key=lambda item: (item.status, item.source_type, item.filename.casefold()))
        return RefreshPlan(
            tuple(files),
            tuple(candidates),
            tuple(scan_issues),
            frozenset(scanned_types),
            folder_errors,
        )

    def refresh(
        self,
        report: ProgressCallback | None = None,
        *,
        plan: RefreshPlan | None = None,
    ) -> RefreshResult:
        report = report or (lambda _event: None)
        analytics_status = self.storage_service.initialize()
        database = analytics_status.database_path
        if database is None:
            raise RuntimeError("Database analytics belum tersedia.")
        derived_was_dirty = self._derived_is_dirty(database)
        report(RefreshProgress("SCANNING", "Scanning files"))
        current_plan = self.prepare_refresh()
        if plan is not None and self._plan_signature(current_plan) != self._plan_signature(plan):
            raise RuntimeError(
                "Source files berubah setelah preview. Jalankan Refresh Data kembali."
            )
        plan = current_plan
        candidates = list(plan.candidates)
        scan_issues = list(plan.scan_issues)
        scanned_types = set(plan.scanned_types)
        folder_errors = plan.folder_errors

        dependency_update = any(
            item.source_type in {SourceType.EMPLOYEE.value, SourceType.SCHEDULE.value}
            and item.status in {SourceStatus.NEW.value, SourceStatus.CHANGED.value}
            for item in plan.files
        )
        if dependency_update and self._has_attendance_rows(database):
            from shared.attendance_ot.backup import verified_backup

            verified_backup(database, "before-master-refresh")

        existing = {
            self._path_key(item.source_path): item for item in self.list_sources()
        }
        seen_paths = {self._path_key(item.path) for item in candidates}
        seen_paths.update(self._path_key(item.path) for item in scan_issues)
        files_processed = 0
        files_skipped = 0
        files_error = folder_errors
        rows_imported = 0
        changed_attendance_source_ids: set[int] = set()
        dependency_changed = False

        for issue in scan_issues:
            self._record_scan_error(database, issue)
            files_error += 1

        total = len(candidates)
        for index, candidate in enumerate(candidates, start=1):
            old = existing.get(self._path_key(candidate.path))
            classification = self._classify(candidate, old)
            if classification is SourceStatus.UNCHANGED:
                self._mark_unchanged(database, candidate, old)
                files_skipped += 1
                continue
            report(
                RefreshProgress(
                    "IMPORTING",
                    f"Importing {index}/{total}: {candidate.filename}",
                    files_processed,
                    files_skipped,
                    files_error,
                    rows_imported,
                )
            )
            source_id = self._ensure_registry(database, candidate, old, classification)
            try:
                imported = self._import_file(
                    database, source_id, candidate, classification
                )
            except Exception as exc:
                files_error += 1
                self._mark_error(database, source_id, candidate, exc)
                logger.exception("Attendance & OT import failed for %s", candidate.path)
                continue
            files_processed += 1
            rows_imported += imported
            if candidate.source_type is SourceType.ATTENDANCE_OT:
                changed_attendance_source_ids.add(source_id)
            else:
                dependency_changed = True

        missing = self._mark_missing(database, scanned_types, seen_paths)
        derived_rows = 0
        if files_processed or self._derived_is_dirty(database):
            report(
                RefreshProgress(
                    "ENRICHING",
                    "Resolving employee, schedule, and analytics",
                    files_processed,
                    files_skipped,
                    files_error,
                    rows_imported,
                )
            )
            enrichment = self.enrichment_service.rebuild(
                database,
                full_rebuild=(
                    derived_was_dirty
                    or dependency_changed
                    or not changed_attendance_source_ids
                ),
                attendance_source_ids=changed_attendance_source_ids,
            )
            derived_rows = enrichment.attendance_rows
        sources = self.list_sources()
        result = RefreshResult(
            files_discovered=len(candidates) + len(scan_issues),
            files_processed=files_processed,
            files_skipped=files_skipped,
            files_error=files_error,
            files_missing=missing,
            rows_imported=rows_imported,
            sources=sources,
            derived_rows=derived_rows,
        )
        report(
            RefreshProgress(
                "COMPLETED",
                "Completed",
                files_processed,
                files_skipped,
                files_error,
                rows_imported,
            )
        )
        return result

    def _scan_sources(
        self,
    ) -> tuple[list[SourceCandidate], list[ScanIssue], set[SourceType], int]:
        core_status = self.storage_service.storage_service.resolve_status()
        if core_status.database_path is None or not core_status.database_valid:
            raise RuntimeError("Database core aktif belum tersedia.")
        preferences = self.database_settings_service.load_attendance_ot_source_preferences(
            core_status.database_path
        )
        configured = {
            SourceType.ATTENDANCE_OT: preferences.attendance_ot_folder,
            SourceType.EMPLOYEE: preferences.employee_folder,
            SourceType.SCHEDULE: preferences.schedule_folder,
        }
        candidates: list[SourceCandidate] = []
        scan_issues: list[ScanIssue] = []
        scanned_types: set[SourceType] = set()
        folder_errors = 0
        for source_type, raw_folder in configured.items():
            if not raw_folder.strip():
                continue
            try:
                found, issues = scan_source_folder(Path(raw_folder), source_type)
                candidates.extend(found)
                scan_issues.extend(issues)
                scanned_types.add(source_type)
            except (OSError, FileNotFoundError) as exc:
                folder_errors += 1
                logger.warning("Attendance & OT source scan failed: %s", exc)
        unique_candidates: dict[str, SourceCandidate] = {}
        for candidate in candidates:
            key = self._path_key(candidate.path)
            previous = unique_candidates.get(key)
            if previous is None:
                unique_candidates[key] = candidate
            elif previous.source_type is not candidate.source_type:
                folder_errors += 1
                logger.warning(
                    "Source file appears in multiple configured folders: %s",
                    candidate.path,
                )
        return list(unique_candidates.values()), scan_issues, scanned_types, folder_errors

    @staticmethod
    def _plan_signature(plan: RefreshPlan) -> tuple:
        return (
            tuple(
                sorted(
                    (
                        item.source_type.value,
                        str(item.path).casefold(),
                        item.fingerprint,
                    )
                    for item in plan.candidates
                )
            ),
            tuple(
                sorted(
                    (item.source_type.value, str(item.path).casefold(), item.error)
                    for item in plan.scan_issues
                )
            ),
            tuple(sorted(value.value for value in plan.scanned_types)),
            plan.folder_errors,
        )

    def list_sources(self) -> tuple[SourceRegistryItem, ...]:
        status = self.storage_service.resolve_status()
        database = status.database_path
        if database is None or not status.database_valid:
            return ()
        with self.factory.connect(database, read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT source_id, source_type, source_path, filename,
                       size_bytes, modified_time_ns, row_count, status,
                       imported_at, fingerprint, error_detail
                FROM source_registry
                ORDER BY source_type, filename COLLATE NOCASE, source_path COLLATE NOCASE
                """
            ).fetchall()
        return tuple(
            SourceRegistryItem(
                source_id=int(row["source_id"]),
                source_type=str(row["source_type"]),
                source_path=Path(str(row["source_path"])),
                filename=str(row["filename"]),
                size_bytes=int(row["size_bytes"]),
                modified_time_ns=int(row["modified_time_ns"]),
                row_count=int(row["row_count"]),
                status=str(row["status"]),
                imported_at=(
                    str(row["imported_at"]) if row["imported_at"] is not None else None
                ),
                fingerprint=(
                    str(row["fingerprint"]) if row["fingerprint"] is not None else None
                ),
                error_detail=(
                    str(row["error_detail"])
                    if row["error_detail"] is not None
                    else None
                ),
            )
            for row in rows
        )

    @staticmethod
    def _classify(
        candidate: SourceCandidate,
        old: SourceRegistryItem | None,
    ) -> SourceStatus:
        if old is None or old.imported_at is None:
            return SourceStatus.NEW
        if old.status == SourceStatus.ERROR:
            return SourceStatus.CHANGED
        if old.fingerprint == candidate.fingerprint:
            return SourceStatus.UNCHANGED
        return SourceStatus.CHANGED

    def _ensure_registry(
        self,
        database: Path,
        candidate: SourceCandidate,
        old: SourceRegistryItem | None,
        classification: SourceStatus,
    ) -> int:
        timestamp = current_timestamp()
        with self.factory.connect(database) as connection:
            if old is None:
                cursor = connection.execute(
                    """
                    INSERT INTO source_registry (
                        source_type, source_path, filename, size_bytes,
                        modified_time_ns, row_count, status, imported_at,
                        fingerprint, error_detail, last_seen_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 0, ?, NULL, ?, NULL, ?, ?, ?)
                    """,
                    (
                        candidate.source_type.value,
                        str(candidate.path),
                        candidate.filename,
                        candidate.size_bytes,
                        candidate.modified_time_ns,
                        classification.value,
                        candidate.fingerprint,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
                return int(cursor.lastrowid)
            connection.execute(
                """
                UPDATE source_registry
                SET source_type=?, filename=?, size_bytes=?, modified_time_ns=?,
                    status=?, fingerprint=?, error_detail=NULL,
                    last_seen_at=?, updated_at=?
                WHERE source_id=?
                """,
                (
                    candidate.source_type.value,
                    candidate.filename,
                    candidate.size_bytes,
                    candidate.modified_time_ns,
                    classification.value,
                    candidate.fingerprint,
                    timestamp,
                    timestamp,
                    old.source_id,
                ),
            )
            return old.source_id

    def _import_file(
        self,
        database: Path,
        source_id: int,
        candidate: SourceCandidate,
        classification: SourceStatus,
    ) -> int:
        imported = 0
        batches: dict[str, list[tuple[object, ...]]] = {}
        timestamp = current_timestamp()
        with self.factory.connect(database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if candidate.source_type is SourceType.ATTENDANCE_OT:
                connection.execute(
                    "DELETE FROM enriched_attendance WHERE source_id=?", (source_id,)
                )
            elif candidate.source_type is SourceType.EMPLOYEE:
                connection.execute("DELETE FROM analytics_monthly_employee")
                connection.execute("DELETE FROM enriched_attendance")
                connection.execute("DELETE FROM employee_snapshots")
            else:
                connection.execute("DELETE FROM analytics_monthly_employee")
                connection.execute("DELETE FROM enriched_attendance")
                connection.execute("DELETE FROM schedule_rule_master")
            for target in (
                "attendance_records",
                "employee_records",
                "schedule_records",
                "schedule_rule_records",
            ):
                connection.execute(
                    f"DELETE FROM {target} WHERE source_id=?", (source_id,)
                )
            for row in iter_source_rows(candidate.path, candidate.source_type):
                table, sql, values = self._database_row(source_id, candidate, row)
                batch = batches.setdefault(table, [])
                batch.append(values)
                if len(batch) >= self.batch_size:
                    connection.executemany(sql, batch)
                    imported += len(batch)
                    batch.clear()
            for table, batch in batches.items():
                if batch:
                    connection.executemany(self._insert_contract(table), batch)
                    imported += len(batch)
            connection.execute(
                """
                UPDATE source_registry
                SET row_count=?, status=?, imported_at=?, error_detail=NULL,
                    last_seen_at=?, updated_at=?
                WHERE source_id=?
                """,
                (
                    imported,
                    classification.value,
                    timestamp,
                    timestamp,
                    timestamp,
                    source_id,
                ),
            )
            connection.execute(
                "UPDATE analytics_metadata SET derived_dirty=1, derived_error=NULL WHERE metadata_id=1"
            )
            connection.commit()
        logger.info("Imported %s rows from %s", imported, candidate.path)
        return imported

    @staticmethod
    def _insert_contract(table: str) -> str:
        if table == "attendance_records":
            placeholders = 16
        elif table == "employee_records":
            placeholders = 15
        elif table == "schedule_rule_records":
            placeholders = 10
        else:
            placeholders = 10
        return f"INSERT INTO {table} VALUES (NULL, {', '.join('?' for _ in range(placeholders))})"

    def _database_row(
        self,
        source_id: int,
        candidate: SourceCandidate,
        row: ParsedSourceRow,
    ) -> tuple[str, str, tuple[object, ...]]:
        def get(name: str) -> object:
            return self._value(row, name)

        common = (
            source_id,
            str(candidate.path),
            row.source_sheet,
            row.source_row,
            identifier_text(get("emplid")),
        )
        if row.source_type is SourceType.ATTENDANCE_OT:
            values = common + (
                date_text(get("date in")),
                time_text(get("time in")),
                date_text(get("date out")),
                time_text(get("time out")),
                numeric_value(get("overtime hour")),
                numeric_value(get("overtime minute")),
                numeric_value(get("ot amount")),
                numeric_value(get("meal ot amount")),
                text_value(get("location descr")),
                text_value(get("name")),
                text_value(get("paylink")),
            )
            table = "attendance_records"
            return table, self._insert_contract(table), values
        if row.source_type is SourceType.EMPLOYEE:
            known = {
                "emplid",
                "name",
                "pay group",
                "status",
                "location descr",
                "regional",
                "dept desc",
                "business desc",
                "jobcd desc",
                "snapshot date",
                "effdt",
            }
            extras = {
                name: text_value(row.values[index])
                for name, index in row.headers.items()
                if name not in known
                and index < len(row.values)
                and text_value(row.values[index]) is not None
            }
            values = common + (
                text_value(get("name")),
                text_value(get("pay group")),
                text_value(get("status")),
                text_value(get("location descr")),
                text_value(get("regional")),
                text_value(get("dept desc")),
                json.dumps(extras, ensure_ascii=False, separators=(",", ":")),
                period_date_text(get("snapshot date") or get("effdt")),
                text_value(get("business desc")),
                text_value(get("jobcd desc")),
            )
            table = "employee_records"
            return table, self._insert_contract(table), values
        if row.schedule_subtype is ScheduleSubtype.RULE:
            rule_text = next(
                (
                    text_value(get(name))
                    for name in (
                        "keterangan",
                        "rule",
                        "schedule rule",
                        "working hours",
                        "jam kerja",
                    )
                    if text_value(get(name)) is not None
                ),
                None,
            )
            values = (
                source_id,
                str(candidate.path),
                row.source_sheet,
                row.source_row,
                text_value(get("schedule id")),
                text_value(get("schedule descr")),
                rule_text,
                time_text(get("scheduled in") or get("time in")),
                time_text(get("scheduled out") or get("time out")),
                text_value(get("weekday") or get("workday")),
            )
            table = "schedule_rule_records"
            return table, self._insert_contract(table), values
        values = common + (
            text_value(get("schedule id")),
            text_value(get("schedule descr")),
            date_text(get("effdt")),
            date_text(get("end effdt")),
            text_value(get("rotation")),
        )
        table = "schedule_records"
        return table, self._insert_contract(table), values

    @staticmethod
    def _value(row: ParsedSourceRow, name: str) -> object:
        index = row.headers.get(name)
        if index is None or index >= len(row.values):
            return None
        return row.values[index]

    def _mark_unchanged(
        self,
        database: Path,
        candidate: SourceCandidate,
        old: SourceRegistryItem | None,
    ) -> None:
        if old is None:
            return
        timestamp = current_timestamp()
        with self.factory.connect(database) as connection:
            connection.execute(
                """
                UPDATE source_registry
                SET status='UNCHANGED', filename=?, size_bytes=?, modified_time_ns=?,
                    fingerprint=?, error_detail=NULL, last_seen_at=?, updated_at=?
                WHERE source_id=?
                """,
                (
                    candidate.filename,
                    candidate.size_bytes,
                    candidate.modified_time_ns,
                    candidate.fingerprint,
                    timestamp,
                    timestamp,
                    old.source_id,
                ),
            )

    def _mark_error(
        self,
        database: Path,
        source_id: int,
        candidate: SourceCandidate,
        error: Exception,
    ) -> None:
        timestamp = current_timestamp()
        detail = self._friendly_error(error)
        with self.factory.connect(database) as connection:
            connection.execute(
                """
                UPDATE source_registry
                SET status='ERROR', filename=?, size_bytes=?, modified_time_ns=?,
                    fingerprint=?, error_detail=?, last_seen_at=?, updated_at=?
                WHERE source_id=?
                """,
                (
                    candidate.filename,
                    candidate.size_bytes,
                    candidate.modified_time_ns,
                    candidate.fingerprint,
                    detail,
                    timestamp,
                    timestamp,
                    source_id,
                ),
            )

    def _record_scan_error(self, database: Path, issue: ScanIssue) -> None:
        timestamp = current_timestamp()
        with self.factory.connect(database) as connection:
            connection.execute(
                """
                INSERT INTO source_registry (
                    source_type, source_path, filename, size_bytes,
                    modified_time_ns, row_count, status, imported_at,
                    fingerprint, error_detail, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 'ERROR', NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    source_type=excluded.source_type,
                    filename=excluded.filename,
                    size_bytes=excluded.size_bytes,
                    modified_time_ns=excluded.modified_time_ns,
                    status='ERROR', error_detail=excluded.error_detail,
                    last_seen_at=excluded.last_seen_at,
                    updated_at=excluded.updated_at
                """,
                (
                    issue.source_type.value,
                    str(issue.path),
                    issue.filename,
                    issue.size_bytes,
                    issue.modified_time_ns,
                    issue.error[:2000],
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )

    def _mark_missing(
        self,
        database: Path,
        scanned_types: set[SourceType],
        seen_paths: set[str],
    ) -> int:
        if not scanned_types:
            return 0
        timestamp = current_timestamp()
        missing_ids: list[int] = []
        for item in self.list_sources():
            if (
                item.source_type in {value.value for value in scanned_types}
                and self._path_key(item.source_path) not in seen_paths
                and item.status != SourceStatus.MISSING
            ):
                missing_ids.append(item.source_id)
        if not missing_ids:
            return 0
        with self.factory.connect(database) as connection:
            connection.executemany(
                """
                UPDATE source_registry
                SET status='MISSING', error_detail='File tidak ditemukan saat refresh.',
                    updated_at=? WHERE source_id=?
                """,
                ((timestamp, source_id) for source_id in missing_ids),
            )
        return len(missing_ids)

    @staticmethod
    def _path_key(path: Path) -> str:
        return str(path).replace("/", "\\").casefold()

    @staticmethod
    def _friendly_error(error: Exception) -> str:
        if isinstance(error, (OSError, ValueError, sqlite3.Error)):
            return str(error)[:2000]
        return f"File gagal diimport: {error}"[:2000]

    def _derived_is_dirty(self, database: Path) -> bool:
        with self.factory.connect(database, read_only=True) as connection:
            row = connection.execute(
                "SELECT derived_dirty FROM analytics_metadata WHERE metadata_id=1"
            ).fetchone()
        return row is not None and bool(row["derived_dirty"])

    def _has_attendance_rows(self, database: Path) -> bool:
        with self.factory.connect(database, read_only=True) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM attendance_records LIMIT 1"
                ).fetchone()
                is not None
            )
