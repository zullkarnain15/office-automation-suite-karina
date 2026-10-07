"""Transactional, batched import orchestration for Attendance & OT sources."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from shared.attendance_ot.models import (
    DataUpdateResult,
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
        batch_size: int = 10_000,
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

    def update_source(
        self,
        source_type: SourceType | str,
        report: ProgressCallback | None = None,
        *,
        _rebuild_analytics: bool = True,
        _changed_attendance_source_ids: set[int] | None = None,
        _changed_attendance_months: set[str] | None = None,
        _changed_employee_dates: dict[str, str] | None = None,
        _changed_schedule_dates: dict[str, str] | None = None,
        _changed_schedule_rule_keys: set[str] | None = None,
    ) -> DataUpdateResult:
        """Incrementally synchronize one configured source in one transaction."""

        report = report or (lambda _event: None)
        source_type = SourceType(source_type)
        timestamp = current_timestamp()
        started_at = perf_counter()
        database: Path | None = None
        candidates: tuple[SourceCandidate, ...] = ()
        files_found = 0
        files_new = 0
        files_changed = 0
        files_skipped = 0
        files_processed = 0
        rows_inserted = 0
        rows_updated = 0
        rows_unchanged = 0
        record_count = 0
        actionable: list[tuple[SourceCandidate, SourceStatus]] = []
        changed_attendance_source_ids: set[int] = set()
        changed_attendance_months: set[str] = set()
        changed_employee_dates: dict[str, str] = {}
        changed_schedule_dates: dict[str, str] = {}
        changed_schedule_rule_keys: set[str] = set()
        try:
            analytics_status = self.storage_service.initialize()
            database = analytics_status.database_path
            if database is None:
                raise RuntimeError("Database analytics belum tersedia.")
            folder = self._configured_folder(source_type)
            report(
                RefreshProgress(
                    "SCANNING",
                    f"Scanning {source_type.value}",
                    percent=5,
                )
            )
            candidates, issues = scan_source_folder(
                folder, source_type, include_fingerprint=False
            )
            files_found = len(candidates) + len(issues)
            if issues:
                detail = "; ".join(
                    f"{issue.filename}: {issue.error}" for issue in issues
                )
                raise ValueError(detail)
            if not candidates:
                raise ValueError(f"Tidak ada file Excel untuk {source_type.value}.")

            with self.factory.connect(database) as connection:
                self._configure_bulk_connection(connection)
                connection.execute("BEGIN IMMEDIATE")
                previous_latest_employees = (
                    self._latest_employee_ids(connection)
                    if source_type is SourceType.EMPLOYEE
                    else set()
                )
                rebound_files = self._rebind_moved_source_files(
                    connection,
                    source_type,
                    candidates,
                    timestamp,
                )
                if rebound_files:
                    # Persist only the portable path mapping.  A later reader
                    # failure can then mark the same registry row as ERROR
                    # instead of creating a duplicate row under the new path.
                    connection.commit()
                    connection.execute("BEGIN IMMEDIATE")
                registry = self._file_registry(connection, source_type)
                for candidate in candidates:
                    classification = self._classify_file(
                        candidate, registry.get(self._path_key(candidate.path))
                    )
                    if (
                        classification is SourceStatus.UNCHANGED
                        and source_type is SourceType.ATTENDANCE_OT
                        and self._needs_attendance_job_title_backfill(
                            connection, candidate
                        )
                    ):
                        classification = SourceStatus.CHANGED
                    if classification is SourceStatus.NEW:
                        files_new += 1
                        actionable.append((candidate, classification))
                    elif classification is SourceStatus.CHANGED:
                        files_changed += 1
                        actionable.append((candidate, classification))
                    else:
                        files_skipped += 1
                        self._mark_file_registry_unchanged(
                            connection, candidate, timestamp
                        )

                raw_index_definitions: tuple[tuple[str, str], ...] = ()
                if (
                    source_type is SourceType.ATTENDANCE_OT
                    and actionable
                    and connection.execute(
                        "SELECT 1 FROM attendance_records LIMIT 1"
                    ).fetchone()
                    is None
                ):
                    raw_index_definitions = self._drop_table_indexes(
                        connection, "attendance_records"
                    )

                total = len(actionable)
                for index, (candidate, classification) in enumerate(
                    actionable, start=1
                ):
                    report(
                        RefreshProgress(
                            "IMPORTING",
                            f"Importing {source_type.value} {index}/{total}: "
                            f"{candidate.filename}",
                            files_processed=files_processed,
                            files_skipped=files_skipped,
                            rows_imported=record_count,
                            percent=10 + round(70 * (index - 1) / max(1, total)),
                        )
                    )
                    source_id = self._ensure_update_registry(
                        connection, candidate, classification, timestamp
                    )
                    file_rows, inserted, updated, unchanged = self._sync_candidate(
                        connection,
                        source_id,
                        candidate,
                        changed_attendance_months=changed_attendance_months,
                        changed_employee_dates=changed_employee_dates,
                        changed_schedule_dates=changed_schedule_dates,
                        changed_schedule_rule_keys=changed_schedule_rule_keys,
                        progress=lambda rows, index=index, total=total,
                        candidate=candidate: report(
                            RefreshProgress(
                                "IMPORTING",
                                f"Importing {source_type.value} {index}/{total}: "
                                f"{candidate.filename} ({rows:,} rows)",
                                files_processed=files_processed,
                                files_skipped=files_skipped,
                                rows_imported=record_count + rows,
                                percent=(
                                    10
                                    + round(70 * (index - 1) / max(1, total))
                                ),
                            )
                        ),
                    )
                    if file_rows <= 0:
                        raise ValueError(
                            f"File tidak memiliki record: {candidate.filename}."
                        )
                    record_count += file_rows
                    rows_inserted += inserted
                    rows_updated += updated
                    rows_unchanged += unchanged
                    if source_type is SourceType.ATTENDANCE_OT and (
                        inserted or updated
                    ):
                        changed_attendance_source_ids.add(source_id)
                    files_processed += 1
                    self._finish_file_import(
                        connection,
                        source_id,
                        candidate,
                        classification,
                        timestamp,
                        file_rows,
                    )

                if raw_index_definitions:
                    self._restore_indexes(connection, raw_index_definitions)

                if source_type is SourceType.EMPLOYEE and changed_employee_dates:
                    current_latest_employees = self._latest_employee_ids(connection)
                    for emplid in (
                        previous_latest_employees ^ current_latest_employees
                    ):
                        changed_employee_dates[emplid] = "0001-01-01"

                if (rows_inserted or rows_updated) and _rebuild_analytics:
                    report(
                        RefreshProgress(
                            "ENRICHING",
                            f"Rebuilding analytics after {source_type.value}",
                            files_processed=files_processed,
                            files_skipped=files_skipped,
                            rows_imported=record_count,
                            percent=85,
                        )
                    )
                    analytics_empty = (
                        connection.execute(
                            "SELECT 1 FROM enriched_attendance LIMIT 1"
                        ).fetchone()
                        is None
                    )
                    dependency_scope = (
                        changed_employee_dates
                        if source_type is SourceType.EMPLOYEE
                        else changed_schedule_dates
                        if source_type is SourceType.SCHEDULE
                        else None
                    )
                    dependency_change_without_scope = (
                        source_type in {SourceType.EMPLOYEE, SourceType.SCHEDULE}
                        and not dependency_scope
                        and not changed_schedule_rule_keys
                    )
                    self.enrichment_service.rebuild_connection(
                        connection,
                        full_rebuild=(
                            analytics_empty
                            or bool(changed_schedule_rule_keys)
                            or dependency_change_without_scope
                        ),
                        attendance_source_ids=changed_attendance_source_ids,
                        employee_scope=dependency_scope,
                        additional_impacted_months=changed_attendance_months,
                    )
                elif rows_inserted or rows_updated:
                    connection.execute(
                        "UPDATE analytics_metadata "
                        "SET derived_dirty=1, derived_error=NULL "
                        "WHERE metadata_id=1"
                    )
                duration = perf_counter() - started_at
                result = DataUpdateResult(
                    source_type=source_type.value,
                    last_update=timestamp,
                    file_count=files_found,
                    record_count=record_count,
                    status="SUCCESS",
                    files_found=files_found,
                    files_new=files_new,
                    files_changed=files_changed,
                    files_skipped=files_skipped,
                    files_processed=files_processed,
                    rows_inserted=rows_inserted,
                    rows_updated=rows_updated,
                    rows_unchanged=rows_unchanged,
                    duration_seconds=duration,
                )
                self._write_data_update_status(connection, result)
                connection.commit()
            if _changed_attendance_source_ids is not None:
                _changed_attendance_source_ids.update(
                    changed_attendance_source_ids
                )
            if _changed_attendance_months is not None:
                _changed_attendance_months.update(changed_attendance_months)
            self._merge_change_scope(
                _changed_employee_dates, changed_employee_dates
            )
            self._merge_change_scope(
                _changed_schedule_dates, changed_schedule_dates
            )
            if _changed_schedule_rule_keys is not None:
                _changed_schedule_rule_keys.update(
                    changed_schedule_rule_keys
                )
            report(
                RefreshProgress(
                    "COMPLETED",
                    f"Completed {source_type.value}",
                    files_processed=files_processed,
                    files_skipped=files_skipped,
                    rows_imported=record_count,
                    percent=100,
                )
            )
            return result
        except Exception as exc:
            detail = self._friendly_error(exc)
            logger.exception("Data Update failed for %s", source_type.value)
            duration = perf_counter() - started_at
            result = DataUpdateResult(
                source_type=source_type.value,
                last_update=timestamp,
                file_count=files_found,
                record_count=0,
                status="ERROR",
                error_detail=detail,
                files_found=files_found,
                files_new=files_new,
                files_changed=files_changed,
                files_skipped=files_skipped,
                files_processed=0,
                duration_seconds=duration,
            )
            if database is not None:
                with self.factory.connect(database) as connection:
                    for candidate, _classification in actionable:
                        self._mark_file_registry_error(
                            connection, candidate, timestamp, detail
                        )
                    self._write_data_update_status(connection, result)
            return result

    def update_all(
        self, report: ProgressCallback | None = None
    ) -> tuple[DataUpdateResult, ...]:
        """Import each source independently, then rebuild analytics only once."""

        report = report or (lambda _event: None)
        changed_attendance_source_ids: set[int] = set()
        changed_attendance_months: set[str] = set()
        changed_employee_dates: dict[str, str] = {}
        changed_schedule_dates: dict[str, str] = {}
        changed_schedule_rule_keys: set[str] = set()
        source_types = (
            SourceType.EMPLOYEE,
            SourceType.SCHEDULE,
            SourceType.ATTENDANCE_OT,
        )
        results_list: list[DataUpdateResult] = []
        for source_index, source_type in enumerate(source_types):
            def segmented_report(
                event: RefreshProgress,
                *,
                index: int = source_index,
            ) -> None:
                inner_percent = event.percent or 0
                overall_percent = min(
                    85,
                    round(
                        (index + inner_percent / 100)
                        / len(source_types)
                        * 85
                    ),
                )
                report(
                    RefreshProgress(
                        phase=event.phase,
                        message=event.message,
                        files_processed=event.files_processed,
                        files_skipped=event.files_skipped,
                        files_error=event.files_error,
                        rows_imported=event.rows_imported,
                        percent=overall_percent,
                    )
                )

            results_list.append(
                self.update_source(
                    source_type,
                    segmented_report,
                    _rebuild_analytics=False,
                    _changed_attendance_source_ids=changed_attendance_source_ids,
                    _changed_attendance_months=changed_attendance_months,
                    _changed_employee_dates=changed_employee_dates,
                    _changed_schedule_dates=changed_schedule_dates,
                    _changed_schedule_rule_keys=changed_schedule_rule_keys,
                )
            )
        results = tuple(results_list)
        changed = tuple(
            result
            for result in results
            if result.status == "SUCCESS"
            and (result.rows_inserted or result.rows_updated)
        )
        if not changed:
            report(RefreshProgress("COMPLETED", "Completed", percent=100))
            return results

        dependency_changed = any(
            result.source_type
            in {SourceType.EMPLOYEE.value, SourceType.SCHEDULE.value}
            for result in changed
        )
        dependency_scope: dict[str, str] = {}
        self._merge_change_scope(dependency_scope, changed_employee_dates)
        self._merge_change_scope(dependency_scope, changed_schedule_dates)
        status = self.storage_service.initialize()
        database = status.database_path
        if database is None:
            raise RuntimeError("Database analytics belum tersedia.")
        report(
            RefreshProgress(
                "ENRICHING",
                "Rebuilding analytics once after all imports",
                files_processed=sum(item.files_processed for item in results),
                files_skipped=sum(item.files_skipped for item in results),
                rows_imported=sum(item.record_count for item in results),
                percent=90,
            )
        )
        try:
            with self.factory.connect(database) as connection:
                self._configure_bulk_connection(connection)
                connection.execute("BEGIN IMMEDIATE")
                analytics_empty = (
                    connection.execute(
                        "SELECT 1 FROM enriched_attendance LIMIT 1"
                    ).fetchone()
                    is None
                )
                self.enrichment_service.rebuild_connection(
                    connection,
                    full_rebuild=(
                        analytics_empty
                        or bool(changed_schedule_rule_keys)
                        or (dependency_changed and not dependency_scope)
                    ),
                    attendance_source_ids=changed_attendance_source_ids,
                    employee_scope=dependency_scope,
                    additional_impacted_months=changed_attendance_months,
                )
                connection.commit()
        except Exception as exc:
            with self.factory.connect(database) as connection:
                connection.execute(
                    "UPDATE analytics_metadata "
                    "SET derived_dirty=1, derived_error=? WHERE metadata_id=1",
                    (str(exc)[:2000],),
                )
            raise
        report(RefreshProgress("COMPLETED", "Completed", percent=100))
        return results

    def data_update_statuses(self) -> tuple[DataUpdateResult, ...]:
        status = self.storage_service.initialize()
        database = status.database_path
        if database is None:
            raise RuntimeError("Database analytics belum tersedia.")
        with self.factory.connect(database, read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT source_type, last_update, file_count, record_count,
                       status, error_detail, files_found, files_new,
                       files_changed, files_skipped, files_processed,
                       rows_inserted, rows_updated, rows_unchanged,
                       duration_seconds
                FROM data_update_status
                ORDER BY CASE source_type
                    WHEN 'EMPLOYEE' THEN 1
                    WHEN 'SCHEDULE' THEN 2 ELSE 3 END
                """
            ).fetchall()
        return tuple(
            DataUpdateResult(
                source_type=str(row["source_type"]),
                last_update=str(row["last_update"] or ""),
                file_count=int(row["file_count"]),
                record_count=int(row["record_count"]),
                status=str(row["status"]),
                error_detail=(
                    str(row["error_detail"]) if row["error_detail"] else None
                ),
                files_found=int(row["files_found"]),
                files_new=int(row["files_new"]),
                files_changed=int(row["files_changed"]),
                files_skipped=int(row["files_skipped"]),
                files_processed=int(row["files_processed"]),
                rows_inserted=int(row["rows_inserted"]),
                rows_updated=int(row["rows_updated"]),
                rows_unchanged=int(row["rows_unchanged"]),
                duration_seconds=float(row["duration_seconds"]),
            )
            for row in rows
        )

    def _configured_folder(self, source_type: SourceType) -> Path:
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
        raw_folder = configured[source_type].strip()
        if not raw_folder:
            raise ValueError(f"Folder {source_type.value} belum diatur di Settings.")
        return Path(raw_folder)

    @staticmethod
    def _file_registry(connection, source_type: SourceType) -> dict[str, sqlite3.Row]:
        rows = connection.execute(
            """
            SELECT full_path, file_size, modified_time_ns, last_imported, status
            FROM source_file_registry
            WHERE source_type=?
            """,
            (source_type.value,),
        ).fetchall()
        return {
            AttendanceOTImportService._path_key(Path(str(row["full_path"]))): row
            for row in rows
        }

    @staticmethod
    def _rebind_moved_source_files(
        connection,
        source_type: SourceType,
        candidates: tuple[SourceCandidate, ...],
        timestamp: str,
    ) -> int:
        """Rebind unique filenames after a database moves to another PC."""

        rows = connection.execute(
            "SELECT full_path FROM source_file_registry WHERE source_type=?",
            (source_type.value,),
        ).fetchall()
        registered = {
            AttendanceOTImportService._path_key(Path(str(row["full_path"]))): row
            for row in rows
        }
        candidate_keys = {
            AttendanceOTImportService._path_key(candidate.path)
            for candidate in candidates
        }
        unmatched_candidates: dict[str, list[SourceCandidate]] = {}
        for candidate in candidates:
            key = AttendanceOTImportService._path_key(candidate.path)
            if key not in registered:
                unmatched_candidates.setdefault(
                    candidate.filename.casefold(), []
                ).append(candidate)

        stale_paths: dict[str, list[Path]] = {}
        for key, row in registered.items():
            if key not in candidate_keys:
                old_path = Path(str(row["full_path"]))
                stale_paths.setdefault(old_path.name.casefold(), []).append(old_path)

        rebound = 0
        for filename, new_items in unmatched_candidates.items():
            old_items = stale_paths.get(filename, [])
            if not old_items:
                continue
            if len(new_items) != 1 or len(old_items) != 1:
                raise ValueError(
                    "Rebind source ambigu untuk file "
                    f"{filename!r}. Pastikan hanya ada satu file dengan nama "
                    "tersebut pada folder source lokal."
                )
            old_path = old_items[0]
            candidate = new_items[0]
            connection.execute(
                "UPDATE source_registry SET source_path=?, filename=?, "
                "updated_at=? WHERE source_path=? AND source_type=?",
                (
                    str(candidate.path),
                    candidate.filename,
                    timestamp,
                    str(old_path),
                    source_type.value,
                ),
            )
            cursor = connection.execute(
                "UPDATE source_file_registry SET full_path=?, updated_at=? "
                "WHERE full_path=? AND source_type=?",
                (
                    str(candidate.path),
                    timestamp,
                    str(old_path),
                    source_type.value,
                ),
            )
            rebound += max(0, int(cursor.rowcount))
        return rebound

    @staticmethod
    def _classify_file(
        candidate: SourceCandidate, old: sqlite3.Row | None
    ) -> SourceStatus:
        if old is None or old["last_imported"] is None:
            return SourceStatus.NEW
        if str(old["status"]) == SourceStatus.ERROR.value:
            return SourceStatus.CHANGED
        if (
            int(old["file_size"]) == candidate.size_bytes
            and int(old["modified_time_ns"]) == candidate.modified_time_ns
        ):
            return SourceStatus.UNCHANGED
        return SourceStatus.CHANGED

    @staticmethod
    def _mark_file_registry_unchanged(
        connection, candidate: SourceCandidate, timestamp: str
    ) -> None:
        connection.execute(
            """
            UPDATE source_file_registry
            SET status='UNCHANGED', error_detail=NULL, updated_at=?
            WHERE full_path=?
            """,
            (timestamp, str(candidate.path)),
        )
        connection.execute(
            """
            UPDATE source_registry
            SET status='UNCHANGED', error_detail=NULL, last_seen_at=?, updated_at=?
            WHERE source_path=?
            """,
            (timestamp, timestamp, str(candidate.path)),
        )

    @staticmethod
    def _ensure_update_registry(
        connection,
        candidate: SourceCandidate,
        classification: SourceStatus,
        timestamp: str,
    ) -> int:
        old = connection.execute(
            "SELECT source_id, source_type FROM source_registry WHERE source_path=?",
            (str(candidate.path),),
        ).fetchone()
        if old is not None:
            if str(old["source_type"]) != candidate.source_type.value:
                raise ValueError(
                    f"Source type berubah untuk file {candidate.filename}."
                )
            connection.execute(
                """
                UPDATE source_registry
                SET filename=?, size_bytes=?, modified_time_ns=?, status=?,
                    fingerprint=NULL, error_detail=NULL, last_seen_at=?, updated_at=?
                WHERE source_id=?
                """,
                (
                    candidate.filename,
                    candidate.size_bytes,
                    candidate.modified_time_ns,
                    classification.value,
                    timestamp,
                    timestamp,
                    int(old["source_id"]),
                ),
            )
            return int(old["source_id"])
        cursor = connection.execute(
            """
            INSERT INTO source_registry (
                source_type, source_path, filename, size_bytes,
                modified_time_ns, row_count, status, imported_at,
                fingerprint, error_detail, last_seen_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                candidate.source_type.value,
                str(candidate.path),
                candidate.filename,
                candidate.size_bytes,
                candidate.modified_time_ns,
                classification.value,
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def _sync_candidate(
        self,
        connection,
        source_id: int,
        candidate: SourceCandidate,
        *,
        changed_attendance_months: set[str] | None = None,
        changed_employee_dates: dict[str, str] | None = None,
        changed_schedule_dates: dict[str, str] | None = None,
        changed_schedule_rule_keys: set[str] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> tuple[int, int, int, int]:
        states: dict[str, dict[str, object]] = {}
        for table in self._source_tables(candidate.source_type):
            columns = tuple(
                str(row["name"])
                for row in connection.execute(f"PRAGMA table_info({table})")
            )
            primary_key, value_columns = columns[0], columns[1:]
            existing_rows = connection.execute(
                f"SELECT * FROM {table} WHERE source_id=?", (source_id,)
            ).fetchall()
            states[table] = {
                "primary_key": primary_key,
                "value_columns": value_columns,
                "existing": {
                    (str(row["source_sheet"]), int(row["source_row"])): row
                    for row in existing_rows
                },
                "seen": set(),
                "inserts": [],
                "updates": [],
                "update_sql": (
                    f"UPDATE {table} SET "
                    + ", ".join(f"{column}=?" for column in value_columns)
                    + f" WHERE {primary_key}=?"
                ),
            }

        row_count = 0
        inserted = 0
        updated = 0
        unchanged = 0
        for row in iter_source_rows(candidate.path, candidate.source_type):
            table, _sql, values = self._database_row(source_id, candidate, row)
            state = states[table]
            key = (row.source_sheet, row.source_row)
            seen = state["seen"]
            if key in seen:
                raise ValueError(
                    f"Duplicate source row {row.source_sheet}:{row.source_row} "
                    f"di {candidate.filename}."
                )
            seen.add(key)
            row_count += 1
            if progress is not None and row_count % 25_000 == 0:
                progress(row_count)
            existing = state["existing"]
            old = existing.get(key)
            if old is None:
                if candidate.source_type is SourceType.EMPLOYEE:
                    self._track_employee_change(
                        changed_employee_dates, state["value_columns"], values
                    )
                elif candidate.source_type is SourceType.SCHEDULE:
                    self._track_schedule_change(
                        changed_schedule_dates,
                        changed_schedule_rule_keys,
                        table,
                        state["value_columns"],
                        values,
                    )
                batch = state["inserts"]
                batch.append(values)
                if len(batch) >= self.batch_size:
                    connection.executemany(self._insert_contract(table), batch)
                    inserted += len(batch)
                    batch.clear()
            elif tuple(old[column] for column in state["value_columns"]) == values:
                unchanged += 1
            else:
                if candidate.source_type is SourceType.EMPLOYEE:
                    self._track_employee_change(
                        changed_employee_dates,
                        state["value_columns"],
                        tuple(old[column] for column in state["value_columns"]),
                    )
                    self._track_employee_change(
                        changed_employee_dates, state["value_columns"], values
                    )
                elif candidate.source_type is SourceType.SCHEDULE:
                    self._track_schedule_change(
                        changed_schedule_dates,
                        changed_schedule_rule_keys,
                        table,
                        state["value_columns"],
                        tuple(old[column] for column in state["value_columns"]),
                    )
                    self._track_schedule_change(
                        changed_schedule_dates,
                        changed_schedule_rule_keys,
                        table,
                        state["value_columns"],
                        values,
                    )
                batch = state["updates"]
                batch.append(values + (old[state["primary_key"]],))
                if len(batch) >= self.batch_size:
                    connection.executemany(state["update_sql"], batch)
                    updated += len(batch)
                    batch.clear()

        for table, state in states.items():
            inserts = state["inserts"]
            if inserts:
                connection.executemany(self._insert_contract(table), inserts)
                inserted += len(inserts)
            updates = state["updates"]
            if updates:
                connection.executemany(state["update_sql"], updates)
                updated += len(updates)
            primary_key = state["primary_key"]
            stale_ids = [
                (row[primary_key],)
                for key, row in state["existing"].items()
                if key not in state["seen"]
            ]
            if stale_ids:
                if candidate.source_type is SourceType.ATTENDANCE_OT:
                    for offset in range(0, len(stale_ids), 900):
                        identifiers = tuple(
                            item[0] for item in stale_ids[offset : offset + 900]
                        )
                        placeholders = ",".join("?" for _ in identifiers)
                        if changed_attendance_months is not None:
                            changed_attendance_months.update(
                                str(row[0])
                                for row in connection.execute(
                                    "SELECT DISTINCT substr(attendance_date, 1, 7) "
                                    "FROM enriched_attendance WHERE "
                                    f"attendance_record_id IN ({placeholders})",
                                    identifiers,
                                )
                                if row[0]
                            )
                        connection.execute(
                            "DELETE FROM enriched_attendance WHERE "
                            f"attendance_record_id IN ({placeholders})",
                            identifiers,
                        )
                elif candidate.source_type is SourceType.EMPLOYEE:
                    for key, row in state["existing"].items():
                        if key not in state["seen"]:
                            self._track_employee_change(
                                changed_employee_dates,
                                state["value_columns"],
                                tuple(
                                    row[column]
                                    for column in state["value_columns"]
                                ),
                            )
                    connection.executemany(
                        "UPDATE enriched_attendance SET employee_snapshot_id=NULL "
                        "WHERE employee_snapshot_id=("
                        "SELECT employee_snapshot_id FROM employee_snapshots "
                        "WHERE source_employee_record_id=?)",
                        stale_ids,
                    )
                    connection.executemany(
                        "DELETE FROM employee_snapshots "
                        "WHERE source_employee_record_id=?",
                        stale_ids,
                    )
                elif candidate.source_type is SourceType.SCHEDULE:
                    for key, row in state["existing"].items():
                        if key not in state["seen"]:
                            self._track_schedule_change(
                                changed_schedule_dates,
                                changed_schedule_rule_keys,
                                table,
                                state["value_columns"],
                                tuple(
                                    row[column]
                                    for column in state["value_columns"]
                                ),
                            )
                    if table == "schedule_records":
                        connection.executemany(
                            "UPDATE enriched_attendance SET schedule_record_id=NULL "
                            "WHERE schedule_record_id=?",
                            stale_ids,
                        )
                    else:
                        connection.executemany(
                            "DELETE FROM schedule_rule_master "
                            "WHERE source_schedule_rule_record_id=?",
                            stale_ids,
                        )
                connection.executemany(
                    f"DELETE FROM {table} WHERE {primary_key}=?", stale_ids
                )
                updated += len(stale_ids)
        if progress is not None and row_count:
            progress(row_count)
        return row_count, inserted, updated, unchanged

    @staticmethod
    def _track_employee_change(
        changes: dict[str, str] | None,
        columns: tuple[str, ...],
        values: tuple[object, ...],
    ) -> None:
        if changes is None:
            return
        row = dict(zip(columns, values))
        emplid = str(row.get("emplid") or "").strip()
        if not emplid:
            return
        snapshot = str(row.get("snapshot_date") or "").strip() or "0001-01-01"
        previous = changes.get(emplid)
        if previous is None or snapshot < previous:
            changes[emplid] = snapshot

    @staticmethod
    def _track_schedule_change(
        changes: dict[str, str] | None,
        rule_keys: set[str] | None,
        table: str,
        columns: tuple[str, ...],
        values: tuple[object, ...],
    ) -> None:
        row = dict(zip(columns, values))
        if table == "schedule_rule_records":
            if rule_keys is None:
                return
            keys = {
                str(row.get(column) or "").strip().upper()
                for column in ("schedule_id", "schedule_descr")
                if str(row.get(column) or "").strip()
            }
            rule_keys.update(keys or {"*"})
            return
        if changes is None:
            return
        emplid = str(row.get("emplid") or "").strip()
        if not emplid:
            return
        effective_date = str(row.get("effdt") or "").strip() or "0001-01-01"
        previous = changes.get(emplid)
        if previous is None or effective_date < previous:
            changes[emplid] = effective_date

    @staticmethod
    def _merge_change_scope(
        target: dict[str, str] | None,
        source: dict[str, str],
    ) -> None:
        if target is None:
            return
        for emplid, from_date in source.items():
            previous = target.get(emplid)
            if previous is None or from_date < previous:
                target[emplid] = from_date

    @staticmethod
    def _latest_employee_ids(connection) -> set[str]:
        latest = connection.execute(
            """
            SELECT source_id FROM source_registry
            WHERE source_type='EMPLOYEE' AND imported_at IS NOT NULL
              AND status<>'ERROR'
            ORDER BY imported_at DESC, source_id DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is None:
            return set()
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT emplid FROM employee_records WHERE source_id=?",
                (latest[0],),
            )
        }

    @staticmethod
    def _needs_attendance_job_title_backfill(
        connection, candidate: SourceCandidate
    ) -> bool:
        source = connection.execute(
            """
            SELECT source_id FROM source_registry WHERE source_path=?
            """,
            (str(candidate.path),),
        ).fetchone()
        if source is None:
            return False

        # A representative bounded prefix avoids aggregating every attendance
        # row on each unchanged-source scan.  If a migrated source still has no
        # title in the prefix, inspect the same bounded prefix in Excel and
        # force one normal reimport only when the source owns a title column.
        titles = connection.execute(
            "SELECT job_title FROM attendance_records "
            "WHERE source_id=? ORDER BY attendance_record_id LIMIT 1000",
            (source["source_id"],),
        ).fetchall()
        if not titles:
            return False
        if any(text_value(row["job_title"]) for row in titles):
            return False

        # Schema 5 -> 6 added attendance_records.job_title without rewriting
        # the original Excel files.  Inspect only a small prefix and force one
        # normal transactional reimport when the source actually owns a title.
        rows = iter_source_rows(candidate.path, SourceType.ATTENDANCE_OT)
        try:
            for index, row in enumerate(rows):
                for column in ("job title", "jobcd desc"):
                    position = row.headers.get(column)
                    if position is not None and position < len(row.values):
                        if text_value(row.values[position]):
                            return True
                if index >= 999:
                    return False
        finally:
            close = getattr(rows, "close", None)
            if close is not None:
                close()
        return False

    @staticmethod
    def _configure_bulk_connection(connection) -> None:
        """Use a bounded portion of workstation RAM for large SQLite work."""

        connection.execute("PRAGMA cache_size=-262144")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA mmap_size=268435456")

    @staticmethod
    def _drop_table_indexes(
        connection, table: str
    ) -> tuple[tuple[str, str], ...]:
        definitions = tuple(
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL "
                "ORDER BY name",
                (table,),
            )
        )
        for name, _sql in definitions:
            quoted = name.replace('"', '""')
            connection.execute(f'DROP INDEX "{quoted}"')
        return definitions

    @staticmethod
    def _restore_indexes(
        connection, definitions: tuple[tuple[str, str], ...]
    ) -> None:
        for _name, sql in definitions:
            connection.execute(sql)

    @staticmethod
    def _source_tables(source_type: SourceType) -> tuple[str, ...]:
        return {
            SourceType.ATTENDANCE_OT: ("attendance_records",),
            SourceType.EMPLOYEE: ("employee_records",),
            SourceType.SCHEDULE: ("schedule_records", "schedule_rule_records"),
        }[source_type]

    @staticmethod
    def _finish_file_import(
        connection,
        source_id: int,
        candidate: SourceCandidate,
        classification: SourceStatus,
        timestamp: str,
        row_count: int,
    ) -> None:
        connection.execute(
            """
            UPDATE source_registry
            SET row_count=?, status=?, imported_at=?, error_detail=NULL,
                last_seen_at=?, updated_at=?
            WHERE source_id=?
            """,
            (
                row_count,
                classification.value,
                timestamp,
                timestamp,
                timestamp,
                source_id,
            ),
        )
        connection.execute(
            """
            INSERT INTO source_file_registry (
                source_type, full_path, file_size, modified_time_ns,
                last_imported, status, error_detail, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(full_path) DO UPDATE SET
                source_type=excluded.source_type,
                file_size=excluded.file_size,
                modified_time_ns=excluded.modified_time_ns,
                last_imported=excluded.last_imported,
                status=excluded.status,
                error_detail=NULL,
                updated_at=excluded.updated_at
            """,
            (
                candidate.source_type.value,
                str(candidate.path),
                candidate.size_bytes,
                candidate.modified_time_ns,
                timestamp,
                classification.value,
                timestamp,
            ),
        )

    @staticmethod
    def _mark_file_registry_error(
        connection,
        candidate: SourceCandidate,
        timestamp: str,
        detail: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO source_file_registry (
                source_type, full_path, file_size, modified_time_ns,
                last_imported, status, error_detail, updated_at
            ) VALUES (?, ?, ?, ?, NULL, 'ERROR', ?, ?)
            ON CONFLICT(full_path) DO UPDATE SET
                source_type=excluded.source_type,
                file_size=excluded.file_size,
                modified_time_ns=excluded.modified_time_ns,
                status='ERROR',
                error_detail=excluded.error_detail,
                updated_at=excluded.updated_at
            """,
            (
                candidate.source_type.value,
                str(candidate.path),
                candidate.size_bytes,
                candidate.modified_time_ns,
                detail,
                timestamp,
            ),
        )

    @staticmethod
    def _write_data_update_status(
        connection,
        result: DataUpdateResult,
    ) -> None:
        connection.execute(
            """
            INSERT INTO data_update_status (
                source_type, last_update, file_count, record_count,
                status, error_detail, files_found, files_new, files_changed,
                files_skipped, files_processed, rows_inserted, rows_updated,
                rows_unchanged, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_type) DO UPDATE SET
                last_update=excluded.last_update,
                file_count=excluded.file_count,
                record_count=excluded.record_count,
                status=excluded.status,
                error_detail=excluded.error_detail,
                files_found=excluded.files_found,
                files_new=excluded.files_new,
                files_changed=excluded.files_changed,
                files_skipped=excluded.files_skipped,
                files_processed=excluded.files_processed,
                rows_inserted=excluded.rows_inserted,
                rows_updated=excluded.rows_updated,
                rows_unchanged=excluded.rows_unchanged,
                duration_seconds=excluded.duration_seconds
            """,
            (
                result.source_type,
                result.last_update,
                result.file_count,
                result.record_count,
                result.status,
                result.error_detail,
                result.files_found,
                result.files_new,
                result.files_changed,
                result.files_skipped,
                result.files_processed,
                result.rows_inserted,
                result.rows_updated,
                result.rows_unchanged,
                result.duration_seconds,
            ),
        )

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
        report(RefreshProgress("SCANNING", "Scanning files", percent=5))
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
                    10 + round(70 * (index - 1) / max(1, total)),
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
                    85,
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
                100,
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
            placeholders = 17
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
                text_value(get("job title") or get("jobcd desc")),
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
