"""Map the audited Attendance legacy workbook to schema-v1 rows."""

from __future__ import annotations

from typing import Any

from shared.database.importing.legacy.common import (
    key_value_rows,
    table_rows,
    value_of,
)
from shared.database.importing.models import (
    ConfigImportIssue,
    IssueSeverity,
    MappedModuleConfiguration,
    WorkbookData,
)
from shared.database.importing.normalizer import (
    is_development_path,
    normalize_boolean,
    normalize_date,
    normalize_path,
    normalize_workflow,
)
from shared.database.time_utils import current_timestamp


def map_attendance(workbook: WorkbookData) -> MappedModuleConfiguration:
    issues: list[ConfigImportIssue] = []
    timestamp = current_timestamp()
    general = key_value_rows(workbook.sheets["General"])
    output = key_value_rows(workbook.sheets["Output"])

    period_rows = general.get("Payroll_Periode_From", [])
    if len(period_rows) > 1:
        issues.append(
            ConfigImportIssue(
                code="ATTENDANCE_DUPLICATE_PERIOD_KEY",
                severity=IssueSeverity.WARNING,
                module="ATTENDANCE",
                sheet="General",
                row_number=period_rows[1][0].row_number,
                field="Payroll_Periode_From",
                message=(
                    "Duplicate key detected; DB0 maps row 8 to start and "
                    "row 9 to end, requiring confirmation."
                ),
                confirmation_required=True,
            )
        )

    settings = {
        "attendance_settings_id": 1,
        "use_global_output": 1,
        "use_global_period": 1,
        "split_txt_rows": int(value_of(general, "Split_TXT_Rows", 10000)),
        "generate_report_default": normalize_boolean(
            value_of(general, "Generate_Report", "TRUE")
        ),
        "default_workflow": normalize_workflow(
            value_of(general, "Default_Workflow", "HO")
        ),
        "updated_at": timestamp,
    }

    candidates: dict[str, Any] = {}
    output_root = value_of(general, "OutputFolder")
    if output_root is None:
        output_root = value_of(output, "Output_Root")
    if output_root is not None:
        candidates["output_root"] = normalize_path(output_root)
    if len(period_rows) >= 2:
        candidates["period_start"] = normalize_date(
            period_rows[0][1].value
        )
        candidates["period_end"] = normalize_date(
            period_rows[1][1].value
        )

    sources: list[dict[str, Any]] = []
    for workflow, sheet_name, code_field, name_field in (
        ("HO", "MDB_HO", "Company", "Description"),
        ("BRANCH", "MDB_Branch", "Branch_Code", "Branch_Name"),
    ):
        for order, record in enumerate(
            table_rows(
                workbook.sheets[sheet_name],
                required_header="Active",
            ),
            start=1,
        ):
            code = record.get(code_field)
            if code is None or code.value is None:
                continue
            active = normalize_boolean(record["Active"].value)
            path_cell = record.get("MDB_Path")
            path = (
                normalize_path(path_cell.value)
                if path_cell is not None and path_cell.value
                else None
            )
            name_cell = record.get(name_field)
            name = (
                str(name_cell.value).strip()
                if name_cell is not None and name_cell.value is not None
                else ""
            )
            sources.append(
                {
                    "workflow": workflow,
                    "source_code": str(code.value).strip(),
                    "source_name": name,
                    "mdb_path": path,
                    "is_active": active,
                    "sort_order": order,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )
            if path and is_development_path(path):
                issues.append(
                    ConfigImportIssue(
                        code="DEVELOPMENT_PATH_DETECTED",
                        severity=IssueSeverity.WARNING,
                        module="ATTENDANCE",
                        sheet=sheet_name,
                        row_number=code.row_number,
                        field="MDB_Path",
                        message="MDB path appears to be a development path.",
                        proposed_value=path,
                        confirmation_required=bool(active),
                    )
                )
            if "sample" in name.casefold():
                issues.append(
                    ConfigImportIssue(
                        code="SAMPLE_MDB_DETECTED",
                        severity=IssueSeverity.WARNING,
                        module="ATTENDANCE",
                        sheet=sheet_name,
                        row_number=code.row_number,
                        field=name_field,
                        message="Sample Attendance source detected.",
                        proposed_value=name,
                        confirmation_required=bool(active),
                    )
                )

    return MappedModuleConfiguration(
        module="ATTENDANCE",
        tables={
            "attendance_settings": (settings,),
            "attendance_sources": tuple(sources),
        },
        global_candidates=candidates,
        source_file=workbook.detection.path,
        source_hash=workbook.detection.sha256,
        issues=tuple(issues),
    )
