"""Map the audited HRIS legacy workbook to schema-v1 rows."""

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
    is_local_url,
    normalize_boolean,
    normalize_date,
    normalize_path,
    normalize_text_identifier,
    normalize_workflow,
)
from shared.database.time_utils import current_timestamp


def map_hris(workbook: WorkbookData) -> MappedModuleConfiguration:
    issues: list[ConfigImportIssue] = []
    timestamp = current_timestamp()
    general = key_value_rows(workbook.sheets["General"])
    browser = key_value_rows(workbook.sheets["Browser"])
    upload = key_value_rows(workbook.sheets["Upload"])
    url = str(value_of(general, "HRIS_URL", "")).strip()

    if is_local_url(url):
        issues.append(
            ConfigImportIssue(
                code="HRIS_MOCK_URL_DETECTED",
                severity=IssueSeverity.CRITICAL,
                module="HRIS",
                sheet="General",
                field="HRIS_URL",
                message="Local/mock HRIS URL detected.",
                proposed_value=url,
                confirmation_required=True,
            )
        )

    settings = {
        "hris_settings_id": 1,
        "use_global_output": 1,
        "use_global_period": 1,
        "hris_url": url,
        "browser_channel": str(
            value_of(browser, "Browser_Channel", "msedge")
        ).strip(),
        "browser_headless": normalize_boolean(
            value_of(browser, "Headless", "FALSE")
        ),
        "stop_on_first_failure": normalize_boolean(
            value_of(upload, "Stop_On_First_Failure", "TRUE")
        ),
        "click_profile_path": _optional(
            value_of(upload, "Click_Profile_Path")
        ),
        "manual_recovery_enabled": normalize_boolean(
            value_of(upload, "Manual_Recovery_Enabled", "TRUE")
        ),
        "require_profile_match": normalize_boolean(
            value_of(upload, "Require_Profile_Match", "TRUE")
        ),
        "browser_x": int(value_of(upload, "Browser_X", 0)),
        "browser_y": int(value_of(upload, "Browser_Y", 0)),
        "browser_width": int(value_of(upload, "Browser_Width", 1200)),
        "browser_height": int(value_of(upload, "Browser_Height", 800)),
        "browser_zoom": int(value_of(upload, "Browser_Zoom", 100)),
        "verification_enabled": normalize_boolean(
            value_of(upload, "Assisted_Verification_Enabled", "TRUE")
        ),
        "verification_wait_seconds": float(
            value_of(upload, "Verification_Wait_Seconds", 2)
        ),
        "verification_timeout_seconds": float(
            value_of(upload, "Verification_Timeout_Seconds", 30)
        ),
        "verification_poll_seconds": float(
            value_of(upload, "Verification_Poll_Seconds", 1)
        ),
        "verification_success_texts": str(
            value_of(
                upload,
                "Verification_Success_Texts",
                "Process Instance|Submitted|Queued",
            )
        ),
        "verification_failure_texts": str(
            value_of(
                upload,
                "Verification_Failure_Texts",
                "Error|Invalid|Failed",
            )
        ),
        "manual_verification_on_unknown": normalize_boolean(
            value_of(upload, "Manual_Verification_On_Unknown", "TRUE")
        ),
        "manual_verification_on_error": normalize_boolean(
            value_of(upload, "Manual_Verification_On_Error", "TRUE")
        ),
        "updated_at": timestamp,
    }

    candidates: dict[str, Any] = {}
    output_root = value_of(general, "Folder_Upload_Path")
    if output_root:
        candidates["output_root"] = normalize_path(output_root)
        if is_development_path(candidates["output_root"]):
            issues.append(
                ConfigImportIssue(
                    code="DEVELOPMENT_PATH_DETECTED",
                    severity=IssueSeverity.WARNING,
                    module="HRIS",
                    sheet="General",
                    field="Folder_Upload_Path",
                    message="HRIS output path appears project-local.",
                    proposed_value=candidates["output_root"],
                    confirmation_required=True,
                )
            )
    start_date = value_of(upload, "Start_Date")
    end_date = value_of(upload, "End_Date")
    if start_date and end_date:
        candidates["period_start"] = normalize_date(
            start_date,
            legacy_order="MDY",
        )
        candidates["period_end"] = normalize_date(
            end_date,
            legacy_order="MDY",
        )
        issues.append(
            ConfigImportIssue(
                code="FIXED_TESTING_DATE_DETECTED",
                severity=IssueSeverity.WARNING,
                module="HRIS",
                sheet="Upload",
                field="Start_Date/End_Date",
                message="Fixed HRIS dates require confirmation.",
                proposed_value=(
                    f"{candidates['period_start']}.."
                    f"{candidates['period_end']}"
                ),
                confirmation_required=True,
            )
        )

    controls: list[dict[str, Any]] = []
    for record in table_rows(
        workbook.sheets["Run_Control"],
        required_header="Active",
    ):
        id_cell = record.get("Run_Control_ID")
        if id_cell is None or id_cell.value is None:
            continue
        identifier, lossy = normalize_text_identifier(
            id_cell.value,
            number_format=id_cell.number_format,
        )
        if lossy:
            issues.append(
                ConfigImportIssue(
                    code="RUN_CONTROL_ID_TEXT_FORMAT_LOST",
                    severity=IssueSeverity.WARNING,
                    module="HRIS",
                    sheet="Run_Control",
                    row_number=id_cell.row_number,
                    field="Run_Control_ID",
                    message=(
                        "Numeric identifier was converted to TEXT; original "
                        "leading zero cannot be inferred."
                    ),
                    proposed_value=identifier,
                    confirmation_required=True,
                )
            )
        controls.append(
            {
                "workflow": normalize_workflow(
                    record["Workflow"].value
                ),
                "sequence": int(record["Sequence"].value),
                "run_control_id": identifier,
                "description": _optional(
                    record.get("Description").value
                    if record.get("Description")
                    else None
                ),
                "is_active": normalize_boolean(record["Active"].value),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

    steps: list[dict[str, Any]] = []
    if "Assisted_Steps" not in workbook.sheets:
        issues.append(
            ConfigImportIssue(
                code="HRIS_ASSISTED_STEPS_MISSING",
                severity=IssueSeverity.WARNING,
                module="HRIS",
                sheet="Assisted_Steps",
                message=(
                    "Legacy HRIS workbook has no Assisted_Steps sheet; "
                    "replace mode may delete active steps."
                ),
                confirmation_required=True,
            )
        )
    else:
        for record in table_rows(
            workbook.sheets["Assisted_Steps"],
            required_header="Active",
        ):
            if not record.get("Step_Name") or not record["Step_Name"].value:
                continue
            steps.append(
                {
                    "sequence": int(record["Sequence"].value),
                    "step_name": str(record["Step_Name"].value).strip(),
                    "action": str(record["Action"].value).strip(),
                    "input_source": str(
                        record["Input_Source"].value
                    ).strip(),
                    "method": str(record["Method"].value).strip(),
                    "is_required": normalize_boolean(
                        record["Required"].value
                    ),
                    "wait_after_seconds": float(
                        record["Wait_After_Seconds"].value or 0
                    ),
                    "description": _optional(
                        record.get("Description").value
                        if record.get("Description")
                        else None
                    ),
                    "is_active": normalize_boolean(record["Active"].value),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )

    return MappedModuleConfiguration(
        module="HRIS",
        tables={
            "hris_settings": (settings,),
            "hris_run_controls": tuple(controls),
            "hris_assisted_steps": tuple(steps),
        },
        global_candidates=candidates,
        source_file=workbook.detection.path,
        source_hash=workbook.detection.sha256,
        issues=tuple(issues),
    )


def _optional(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value)
