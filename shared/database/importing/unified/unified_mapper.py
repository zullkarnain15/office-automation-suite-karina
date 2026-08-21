"""Map the schema-v1 unified workbook contract to module rows."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
import re
from typing import Any

from shared.database.importing.constants import (
    ATT_DATA_REPAIR_DEFAULT_SETTINGS,
    SINGLETON_IDS,
    UNIFIED_HORIZONTAL_SETTING_SHEETS,
    UNIFIED_SHEET_TABLES,
    UNIFIED_VERTICAL_SETTING_SHEETS,
)
from shared.database.importing.legacy.common import table_rows
from shared.database.importing.models import (
    ConfigImportIssue,
    IssueSeverity,
    MappedModuleConfiguration,
    WorkbookData,
)
from shared.database.importing.normalizer import (
    normalize_boolean,
    normalize_date,
    normalize_text_identifier,
    normalize_workflow,
)
from shared.database.time_utils import current_timestamp
from shared.payroll_period import normalize_payroll_period

BOOLEAN_COLUMNS = {
    "use_global_output",
    "use_global_period",
    "generate_report_default",
    "is_active",
    "auto_reply_enabled",
    "save_smtp_copy_to_sent",
    "browser_headless",
    "stop_on_first_failure",
    "manual_recovery_enabled",
    "require_profile_match",
    "verification_enabled",
    "manual_verification_on_unknown",
    "manual_verification_on_error",
    "is_required",
    "enabled",
    "generate_txt",
    "generate_excel_report",
}
INTEGER_COLUMNS = {
    "split_txt_rows",
    "sort_order",
    "smtp_port",
    "smtp_timeout_seconds",
    "txt_max_lines",
    "browser_x",
    "browser_y",
    "browser_width",
    "browser_height",
    "browser_zoom",
    "sequence",
    "minimum_duration_minutes",
    "txt_max_rows",
}
ATT_DATA_REPAIR_TIME_COLUMNS = {
    "weekday_default_in",
    "weekday_default_out",
    "saturday_default_in",
    "saturday_default_out",
    "saturday_missing_out_default",
    "sunday_invalid_default_in",
    "sunday_invalid_default_out",
    "midnight_time_out_default",
}
REAL_COLUMNS = {
    "verification_wait_seconds",
    "verification_timeout_seconds",
    "verification_poll_seconds",
    "wait_after_seconds",
}
WORKFLOW_COLUMNS = {"workflow", "default_workflow"}
DATE_COLUMNS = {"period_start", "period_end"}
EMPTY_TEXT_COLUMNS = {"company_code", "branch_code"}
SENDER_WORKFLOW_BY_SHEET = {
    "Outlook_HO_Senders": "HO",
    "Outlook_Branch_Senders": "BRANCH",
}


def map_unified(
    workbook: WorkbookData,
) -> tuple[MappedModuleConfiguration, ...]:
    """Map all unified sheets into independent module payloads."""

    module_tables: dict[str, dict[str, tuple[dict[str, Any], ...]]] = defaultdict(
        dict
    )
    module_issues: dict[str, list[ConfigImportIssue]] = defaultdict(list)
    timestamp = current_timestamp()
    # DB2C routes the Excel-compatible Attachment_Consolidation tab to the
    # unchanged attachment_consolidation_settings SQLite table via constants.
    for sheet_name, (
        module,
        table,
    ) in UNIFIED_VERTICAL_SETTING_SHEETS.items():
        if sheet_name not in workbook.sheets:
            if sheet_name == "Att_Data_Repair":
                row = dict(ATT_DATA_REPAIR_DEFAULT_SETTINGS)
                _complete_singleton(row, table, timestamp)
                module_tables[module][table] = (row,)
                module_issues[module].append(
                    ConfigImportIssue(
                        code="ATT_DATA_REPAIR_DEFAULTS_APPLIED",
                        severity=IssueSeverity.WARNING,
                        module=module,
                        sheet=sheet_name,
                        message=(
                            "Workbook lama tidak memiliki sheet Att_Data_Repair; "
                            "default Blueprint digunakan."
                        ),
                    )
                )
                continue
            continue
        sheet = workbook.sheets[sheet_name]
        vertical = table_rows(sheet, required_header="setting_key")
        if vertical:
            row: dict[str, Any] = (
                dict(ATT_DATA_REPAIR_DEFAULT_SETTINGS)
                if table == "att_data_repair_settings"
                else {}
            )
            for record in vertical:
                key_cell = record.get("setting_key")
                value_cell = record.get("setting_value")
                if key_cell is None or not str(key_cell.value or "").strip():
                    continue
                key = str(key_cell.value).strip()
                if value_cell is None or value_cell.value is None:
                    continue
                row[key] = _normalize_column(
                    table,
                    key,
                    value_cell.value,
                    value_cell.number_format,
                )
            if row:
                _complete_singleton(row, table, timestamp)
                module_tables[module][table] = (row,)
            else:
                module_tables[module][table] = ()
            continue

        # Accept the original DB2A horizontal representation as well.
        _, _, required_header = UNIFIED_HORIZONTAL_SETTING_SHEETS[sheet_name]
        rows = []
        for raw in table_rows(sheet, required_header=required_header):
            row = {
                column: _normalize_column(
                    table,
                    column,
                    cell.value,
                    cell.number_format,
                )
                for column, cell in raw.items()
                if cell.value is not None
            }
            _complete_singleton(row, table, timestamp)
            rows.append(row)
        existing = module_tables[module].get(table, ())
        module_tables[module][table] = (*existing, *rows)

    has_split_sender_sheets = any(
        sheet_name in workbook.sheets for sheet_name in SENDER_WORKFLOW_BY_SHEET
    )
    sender_rows_by_key: dict[
        tuple[str, str, str, str],
        tuple[dict[str, Any], str, int],
    ] = {}
    for sheet_name, (
        module,
        table,
        required_header,
    ) in UNIFIED_SHEET_TABLES.items():
        if sheet_name == "Outlook_Sender_Master" and has_split_sender_sheets:
            continue
        if sheet_name not in workbook.sheets:
            continue
        sheet = workbook.sheets[sheet_name]
        rows = []
        for raw in table_rows(sheet, required_header=required_header):
            row: dict[str, Any] = {}
            row_invalid = False
            implied_workflow = SENDER_WORKFLOW_BY_SHEET.get(sheet_name)
            if implied_workflow is not None:
                row["workflow"] = implied_workflow
            for column, cell in raw.items():
                if cell.value is None:
                    if column in EMPTY_TEXT_COLUMNS:
                        row[column] = ""
                    continue
                try:
                    row[column] = _normalize_column(
                        table,
                        column,
                        cell.value,
                        cell.number_format,
                    )
                except (TypeError, ValueError) as exc:
                    if table != "outlook_sender_master":
                        raise
                    module_issues[module].append(
                        ConfigImportIssue(
                            code="OUTLOOK_SENDER_ROW_INVALID",
                            severity=IssueSeverity.ERROR,
                            module=module,
                            sheet=sheet_name,
                            row_number=cell.row_number,
                            field=column,
                            message=(
                                "Invalid Outlook sender value: "
                                f"{exc}"
                            ),
                            current_value=cell.value,
                        )
                    )
                    row_invalid = True
                    break
            if row_invalid:
                continue
            if table in SINGLETON_IDS:
                id_column, id_value = SINGLETON_IDS[table]
                row[id_column] = id_value
            if "updated_at" not in row:
                row["updated_at"] = timestamp
            if table not in SINGLETON_IDS and table != "global_settings":
                row.setdefault("created_at", timestamp)
            if table == "outlook_sender_master":
                row.setdefault("is_active", 1)
                if not str(row.get("sender_email") or "").strip():
                    if row.get("is_active"):
                        module_issues[module].append(
                            ConfigImportIssue(
                                code="ACTIVE_SENDER_EMAIL_MISSING",
                                severity=IssueSeverity.ERROR,
                                module=module,
                                sheet=sheet_name,
                                row_number=next(iter(raw.values())).row_number,
                                field="sender_email",
                                message="Active sender row has no email address.",
                            )
                        )
                    continue
                sender_key = _outlook_sender_key(row)
                previous = sender_rows_by_key.get(sender_key)
                if previous is not None:
                    previous_sender, previous_sheet, previous_row = previous
                    duplicate_identical = (
                        _outlook_sender_meaningful(previous_sender)
                        == _outlook_sender_meaningful(row)
                    )
                    module_issues[module].append(
                        ConfigImportIssue(
                            code=(
                                "OUTLOOK_SENDER_DUPLICATE_IDENTICAL_IGNORED"
                                if duplicate_identical
                                else "OUTLOOK_SENDER_DUPLICATE"
                            ),
                            severity=(
                                IssueSeverity.WARNING
                                if duplicate_identical
                                else IssueSeverity.ERROR
                            ),
                            module=module,
                            sheet=sheet_name,
                            row_number=next(iter(raw.values())).row_number,
                            field="sender_email",
                            message=(
                                "Identical duplicate Outlook sender was ignored; "
                                if duplicate_identical
                                else "Conflicting duplicate Outlook sender; "
                            )
                            + (
                                "first occurrence is at "
                                f"{previous_sheet} row {previous_row}."
                            ),
                        )
                    )
                    continue
                else:
                    sender_rows_by_key[sender_key] = (
                        row,
                        sheet_name,
                        next(iter(raw.values())).row_number,
                    )
            rows.append(row)
        existing = module_tables[module].get(table, ())
        module_tables[module][table] = (*existing, *rows)

    result = []
    for module, tables in module_tables.items():
        result.append(
            MappedModuleConfiguration(
                module=module,
                tables=tables,
                source_file=workbook.detection.path,
                source_hash=workbook.detection.sha256,
                issues=tuple(module_issues.get(module, ())),
            )
        )
    return tuple(result)


def _outlook_sender_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("workflow") or "").strip().upper(),
        str(row.get("company_code") or "").strip(),
        str(row.get("branch_code") or "").strip(),
        str(row.get("sender_email") or "").strip().casefold(),
    )


def _outlook_sender_meaningful(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"sender_id", "created_at", "updated_at"}
    }


def _complete_singleton(
    row: dict[str, Any],
    table: str,
    timestamp: str,
) -> None:
    id_column, id_value = SINGLETON_IDS[table]
    row[id_column] = id_value
    row.setdefault("updated_at", timestamp)


def _normalize_column(
    table: str,
    column: str,
    value: Any,
    number_format: str,
) -> Any:
    if table == "att_data_repair_settings":
        return _normalize_att_data_repair_column(column, value)
    if column in BOOLEAN_COLUMNS:
        return normalize_boolean(value)
    if column in INTEGER_COLUMNS:
        return int(value)
    if column in REAL_COLUMNS:
        return float(value)
    if column in WORKFLOW_COLUMNS:
        return normalize_workflow(
            value,
            allow_all=column == "workflow",
        )
    if column in DATE_COLUMNS:
        return normalize_date(value)
    if column == "run_control_id":
        return normalize_text_identifier(
            value,
            number_format=number_format,
        )[0]
    if column == "payroll_period":
        return normalize_payroll_period(value, allow_blank=True)
    if isinstance(value, str):
        return value.replace("\r\n", "\n")
    return value


def _normalize_att_data_repair_column(column: str, value: Any) -> Any:
    if column in {
        "enabled",
        "generate_txt",
        "generate_excel_report",
        "use_global_period",
        "use_global_output",
    }:
        if isinstance(value, bool):
            return int(value)
        text = str(value).strip().upper()
        if text == "TRUE":
            return 1
        if text == "FALSE":
            return 0
        raise ValueError(f"Att_Data_Repair boolean invalid: {column}={value!r}")
    if column in {"minimum_duration_minutes", "txt_max_rows"}:
        if isinstance(value, bool):
            raise ValueError(f"Att_Data_Repair integer invalid: {column}={value!r}")
        return int(value)
    if column in ATT_DATA_REPAIR_TIME_COLUMNS:
        if isinstance(value, datetime):
            return value.time().replace(second=0, microsecond=0).strftime("%H:%M")
        if isinstance(value, time):
            return value.replace(second=0, microsecond=0).strftime("%H:%M")
        text = str(value).strip()
        if not re.fullmatch(r"\d{2}:\d{2}", text):
            raise ValueError(f"Att_Data_Repair time invalid: {column}={value!r}")
        hour, minute = (int(part) for part in text.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError(f"Att_Data_Repair time invalid: {column}={value!r}")
        return text
    if isinstance(value, str):
        return value.strip()
    return value
