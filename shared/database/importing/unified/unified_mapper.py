"""Map the schema-v1 unified workbook contract to module rows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from shared.database.importing.constants import (
    SINGLETON_IDS,
    UNIFIED_HORIZONTAL_SETTING_SHEETS,
    UNIFIED_SHEET_TABLES,
    UNIFIED_VERTICAL_SETTING_SHEETS,
)
from shared.database.importing.legacy.common import table_rows
from shared.database.importing.models import (
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
    timestamp = current_timestamp()
    # DB2C routes the Excel-compatible Attachment_Consolidation tab to the
    # unchanged attachment_consolidation_settings SQLite table via constants.
    for sheet_name, (
        module,
        table,
    ) in UNIFIED_VERTICAL_SETTING_SHEETS.items():
        sheet = workbook.sheets[sheet_name]
        vertical = table_rows(sheet, required_header="setting_key")
        if vertical:
            row: dict[str, Any] = {}
            for record in vertical:
                key_cell = record.get("setting_key")
                value_cell = record.get("setting_value")
                if key_cell is None or not str(key_cell.value or "").strip():
                    continue
                key = str(key_cell.value).strip()
                if value_cell is None or value_cell.value is None:
                    continue
                row[key] = _normalize_column(
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
            implied_workflow = SENDER_WORKFLOW_BY_SHEET.get(sheet_name)
            if implied_workflow is not None:
                row["workflow"] = implied_workflow
            for column, cell in raw.items():
                if cell.value is None:
                    if column in EMPTY_TEXT_COLUMNS:
                        row[column] = ""
                    continue
                row[column] = _normalize_column(
                    column,
                    cell.value,
                    cell.number_format,
                )
            if table in SINGLETON_IDS:
                id_column, id_value = SINGLETON_IDS[table]
                row[id_column] = id_value
            if "updated_at" not in row:
                row["updated_at"] = timestamp
            if table not in SINGLETON_IDS and table != "global_settings":
                row.setdefault("created_at", timestamp)
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
            )
        )
    return tuple(result)


def _complete_singleton(
    row: dict[str, Any],
    table: str,
    timestamp: str,
) -> None:
    id_column, id_value = SINGLETON_IDS[table]
    row[id_column] = id_value
    row.setdefault("updated_at", timestamp)


def _normalize_column(
    column: str,
    value: Any,
    number_format: str,
) -> Any:
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
