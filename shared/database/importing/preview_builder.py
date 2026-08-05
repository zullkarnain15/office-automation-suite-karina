"""Build a database comparison preview without performing writes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from shared.database.connection_factory import SQLiteConnectionFactory
from shared.database.importing.constants import (
    MODULE_TABLES,
    TABLE_KEYS,
    TABLE_PRIMARY_KEYS,
)
from shared.database.importing.legacy import (
    map_attendance,
    map_hris,
    map_outlook,
)
from shared.database.importing.models import (
    ChangeOperation,
    ConfigImportChange,
    ConfigImportIssue,
    ConfigImportPreview,
    IssueSeverity,
    MappedModuleConfiguration,
    WorkbookIdentity,
)
from shared.database.importing.validator import validate_mapped_configuration
from shared.database.importing.workbook_reader import read_workbook
from shared.database.importing.unified import map_unified
from shared.database.time_utils import current_timestamp

IGNORED_COMPARISON_COLUMNS = {
    "created_at",
    "updated_at",
    *TABLE_PRIMARY_KEYS.values(),
}


class PreviewBuilder:
    """Read workbooks and compare proposed rows with current SQLite rows."""

    def __init__(
        self,
        connection_factory: SQLiteConnectionFactory | None = None,
    ) -> None:
        self.connection_factory = connection_factory or SQLiteConnectionFactory()

    def build(
        self,
        database_path: str | Path,
        source_files: list[str | Path] | tuple[str | Path, ...],
        *,
        global_resolution: dict[str, Any] | None = None,
    ) -> ConfigImportPreview:
        """Build a read-only preview for legacy workbooks."""

        detections = []
        mapped_modules: list[MappedModuleConfiguration] = []
        issues: list[ConfigImportIssue] = []
        seen_hashes: dict[str, Path] = {}

        for source in source_files:
            workbook, read_issues = read_workbook(source)
            detection = workbook.detection
            detections.append(detection)
            issues.extend(read_issues)
            duplicate = seen_hashes.get(detection.normalized_content_hash)
            if duplicate is not None:
                issues.append(
                    ConfigImportIssue(
                        code="DUPLICATE_WORKBOOK_DETECTED",
                        severity=IssueSeverity.WARNING,
                        module="UNKNOWN",
                        message="Normalized workbook content is duplicated.",
                        current_value=str(duplicate),
                        proposed_value=str(detection.path),
                        confirmation_required=True,
                    )
                )
                continue
            seen_hashes[detection.normalized_content_hash] = detection.path

            mapper = {
                WorkbookIdentity.ATTENDANCE_LEGACY: map_attendance,
                WorkbookIdentity.OUTLOOK_REVISI_LEGACY: map_outlook,
                WorkbookIdentity.HRIS_LEGACY: map_hris,
            }.get(detection.identity)
            try:
                if detection.identity == WorkbookIdentity.OAS_K_UNIFIED:
                    candidates = map_unified(workbook)
                elif mapper is not None:
                    candidates = (mapper(workbook),)
                else:
                    code = (
                        "WORKBOOK_AMBIGUOUS"
                        if detection.identity == WorkbookIdentity.AMBIGUOUS
                        else "WORKBOOK_UNKNOWN"
                    )
                    issues.append(
                        ConfigImportIssue(
                            code=code,
                            severity=IssueSeverity.ERROR,
                            module="UNKNOWN",
                            message=(
                                f"Workbook identity is {detection.identity.value}."
                            ),
                            current_value=str(detection.path),
                        )
                    )
                    continue
            except Exception as exc:
                code = (
                    "WORKBOOK_MAPPING_FAILED"
                )
                issues.append(
                    ConfigImportIssue(
                        code=code,
                        severity=IssueSeverity.ERROR,
                        module="UNKNOWN",
                        message=f"Workbook mapping failed: {exc}",
                        current_value=str(detection.path),
                    )
                )
                continue
            for mapped in candidates:
                validated = MappedModuleConfiguration(
                    module=mapped.module,
                    tables=mapped.tables,
                    global_candidates=mapped.global_candidates,
                    source_file=mapped.source_file,
                    source_hash=mapped.source_hash,
                    issues=validate_mapped_configuration(mapped),
                )
                mapped_modules.append(validated)
                issues.extend(validated.issues)

        global_mapped, global_issues = self._global_mapping(
            mapped_modules,
            global_resolution or {},
        )
        issues.extend(global_issues)
        if global_mapped is not None:
            mapped_modules.append(global_mapped)

        with self.connection_factory.connect(
            database_path,
            read_only=True,
        ) as connection:
            snapshot = database_snapshot_hash(connection)
            changes = tuple(
                change
                for mapped in mapped_modules
                for change in compare_module(connection, mapped)
            )

        warning_count = sum(
            issue.severity == IssueSeverity.WARNING for issue in issues
        )
        error_count = sum(
            issue.severity == IssueSeverity.ERROR for issue in issues
        )
        critical_count = sum(
            issue.severity == IssueSeverity.CRITICAL for issue in issues
        )
        confirmation_required = any(
            issue.confirmation_required for issue in issues
        ) or any(change.destructive for change in changes)

        return ConfigImportPreview(
            source_files=tuple(Path(item) for item in source_files),
            detected_workbooks=tuple(detections),
            modules=tuple(mapped.module for mapped in mapped_modules),
            valid_count=sum(
                change.operation
                not in {ChangeOperation.SKIP, ChangeOperation.UNCHANGED}
                for change in changes
            ),
            warning_count=warning_count,
            error_count=error_count,
            critical_count=critical_count,
            confirmation_required=confirmation_required,
            can_commit=error_count == 0,
            changes=changes,
            issues=tuple(issues),
            generated_at=current_timestamp(),
            database_snapshot_hash=snapshot,
            mapped_modules=tuple(mapped_modules),
        )

    @staticmethod
    def _global_mapping(
        modules: list[MappedModuleConfiguration],
        global_resolution: dict[str, Any],
    ) -> tuple[
        MappedModuleConfiguration | None,
        tuple[ConfigImportIssue, ...],
    ]:
        values: dict[str, list[tuple[str, Any]]] = defaultdict(list)
        for module in modules:
            for field, value in module.global_candidates.items():
                values[field].append((module.module, value))

        issues: list[ConfigImportIssue] = []
        resolved: dict[str, Any] = {}
        for field, candidates in values.items():
            distinct = {str(value) for _, value in candidates}
            if len(distinct) == 1:
                resolved[field] = candidates[0][1]
            elif field in global_resolution:
                resolved[field] = global_resolution[field]
                issues.append(
                    ConfigImportIssue(
                        code="GLOBAL_CONFLICT_RESOLVED",
                        severity=IssueSeverity.WARNING,
                        module="GLOBAL",
                        field=field,
                        message=(
                            "Conflicting legacy values were resolved by an "
                            "explicit preview selection."
                        ),
                        current_value=candidates,
                        proposed_value=global_resolution[field],
                        confirmation_required=True,
                    )
                )
            else:
                code = (
                    "GLOBAL_OUTPUT_CONFLICT"
                    if field == "output_root"
                    else "GLOBAL_PERIOD_CONFLICT"
                )
                issues.append(
                    ConfigImportIssue(
                        code=code,
                        severity=IssueSeverity.ERROR,
                        module="GLOBAL",
                        field=field,
                        message="Legacy workbooks propose conflicting global values.",
                        current_value=candidates,
                        confirmation_required=True,
                    )
                )

        if "output_root" not in resolved:
            return None, tuple(issues)
        period_start = resolved.get("period_start")
        period_end = resolved.get("period_end")
        if (period_start is None) != (period_end is None):
            issues.append(
                ConfigImportIssue(
                    code="GLOBAL_PERIOD_INCOMPLETE",
                    severity=IssueSeverity.ERROR,
                    module="GLOBAL",
                    message="Global period requires both start and end.",
                )
            )
            return None, tuple(issues)
        row = {
            "global_settings_id": 1,
            "output_root": resolved["output_root"],
            "period_start": period_start,
            "period_end": period_end,
            "updated_at": current_timestamp(),
            "updated_by": None,
        }
        return (
            MappedModuleConfiguration(
                module="GLOBAL",
                tables={"global_settings": (row,)},
                global_candidates=resolved,
            ),
            tuple(issues),
        )


def compare_module(
    connection: sqlite3.Connection,
    mapped: MappedModuleConfiguration,
) -> list[ConfigImportChange]:
    """Return row-level insert/update/delete/unchanged changes."""

    changes: list[ConfigImportChange] = []
    for table in MODULE_TABLES[mapped.module]:
        proposed_rows = mapped.tables.get(table, ())
        current_rows = _read_rows(connection, table)
        keys = TABLE_KEYS[table]
        current = {_key(row, keys): row for row in current_rows}
        proposed = {_key(row, keys): row for row in proposed_rows}
        for key in sorted(set(current) | set(proposed), key=str):
            old = current.get(key)
            new = proposed.get(key)
            if old is None:
                operation = ChangeOperation.INSERT
            elif new is None:
                operation = ChangeOperation.DELETE
            elif _meaningful(old) == _meaningful(new):
                operation = ChangeOperation.UNCHANGED
            else:
                operation = ChangeOperation.UPDATE
            changes.append(
                ConfigImportChange(
                    module=mapped.module,
                    setting_scope=table,
                    setting_key=json.dumps(key, ensure_ascii=False),
                    operation=operation,
                    old_value=_json_row(old),
                    new_value=_json_row(new),
                    destructive=operation == ChangeOperation.DELETE,
                )
            )
    return changes


def database_snapshot_hash(connection: sqlite3.Connection) -> str:
    payload: dict[str, Any] = {}
    for tables in MODULE_TABLES.values():
        for table in tables:
            payload[table] = [
                _meaningful(row)
                for row in _read_rows(connection, table)
            ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_rows(
    connection: sqlite3.Connection,
    table: str,
) -> list[dict[str, Any]]:
    columns = [
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    ]
    sql = f"SELECT {', '.join(columns)} FROM {table}"
    return [dict(row) for row in connection.execute(sql).fetchall()]


def _key(row: dict[str, Any], columns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(column, "")) for column in columns)


def _meaningful(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in IGNORED_COMPARISON_COLUMNS and value is not None
    }


def _json_row(row: dict[str, Any] | None) -> str | None:
    if row is None:
        return None
    return json.dumps(
        _meaningful(row),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
