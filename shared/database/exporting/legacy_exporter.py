"""Loss-aware legacy workbook exporters backed by schema-v1 data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment

from shared.database.database_validator import DatabaseValidator
from shared.database.exporting.current_config_exporter import (
    _read_configuration,
)
from shared.database.exporting.exceptions import (
    ConfigExportError,
    LegacyExportUnsupportedError,
)
from shared.database.exporting.models import (
    ExportResult,
    WorkbookValidationResult,
)
from shared.database.exporting.style import (
    set_column_widths,
    style_data_area,
    style_headers,
)
from shared.database.exporting.template_builder import _prepare_output_path
from shared.database.importing.models import WorkbookIdentity
from shared.database.importing.workbook_detector import detect_workbook
from shared.database.time_utils import current_timestamp


def export_attendance_legacy(
    database_path: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool = False,
    create_parent: bool = False,
) -> ExportResult:
    """Export the Attendance subset using its audited legacy sheet contract."""

    configuration, _ = _validated_configuration(database_path)
    output = _prepare_output_path(
        output_path,
        overwrite=overwrite,
        create_parent=create_parent,
    )
    global_row = _one(configuration["global_settings"])
    settings = _one(configuration["attendance_settings"])
    sources = configuration["attendance_sources"]
    workbook = Workbook()
    workbook.remove(workbook.active)

    general = workbook.create_sheet("General")
    _key_value_sheet(
        general,
        (
            ("OutputFolder", global_row.get("output_root")),
            ("Split_TXT_Rows", settings.get("split_txt_rows", 10000)),
            (
                "Generate_Report",
                _boolean(settings.get("generate_report_default", 0)),
            ),
            ("Default_Workflow", settings.get("default_workflow", "HO")),
            ("Payroll_Periode_From", global_row.get("period_start")),
            ("Payroll_Periode_From", global_row.get("period_end")),
        ),
    )

    for workflow, sheet_name, headers in (
        (
            "HO",
            "MDB_HO",
            ("Active", "Company", "Description", "MDB_Path"),
        ),
        (
            "BRANCH",
            "MDB_Branch",
            ("Active", "Branch_Code", "Branch_Name", "MDB_Path"),
        ),
    ):
        rows = []
        for row in sources:
            if row["workflow"] != workflow:
                continue
            rows.append(
                (
                    _boolean(row["is_active"]),
                    row["source_code"],
                    row["source_name"],
                    row["mdb_path"],
                )
            )
        _table_sheet(workbook.create_sheet(sheet_name), headers, rows)

    _key_value_sheet(
        workbook.create_sheet("Output"),
        (("Output_Root", global_row.get("output_root")),),
    )
    _table_sheet(
        workbook.create_sheet("Reference"),
        ("Key", "Value"),
        (),
    )
    return _save_legacy(
        workbook,
        output,
        WorkbookIdentity.ATTENDANCE_LEGACY,
    )


def export_outlook_legacy(
    database_path: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool = False,
    create_parent: bool = False,
) -> ExportResult:
    """Export Outlook Revisi using its module-owned payroll period."""

    configuration, _ = _validated_configuration(database_path)
    output = _prepare_output_path(
        output_path,
        overwrite=overwrite,
        create_parent=create_parent,
    )
    global_row = _one(configuration["global_settings"])
    settings = _one(configuration["outlook_settings"])
    payroll_period = settings.get("payroll_period")
    recipients = configuration["outlook_summary_recipients"]
    recipient_values = {
        recipient_type: ";".join(
            str(row["email_address"])
            for row in recipients
            if row["recipient_type"] == recipient_type and row["is_active"]
        )
        for recipient_type in ("TO", "CC")
    }

    workbook = Workbook()
    workbook.remove(workbook.active)
    general_values = (
        ("Integration_Method", settings.get("integration_method", "OOM_COM")),
        ("Mailbox_SMTP", settings.get("mailbox_smtp")),
        ("Source_Folder", settings.get("source_folder", "Inbox")),
        ("Reply_From_SMTP", settings.get("reply_from_smtp")),
        ("Send_Transport", settings.get("send_transport", "OUTLOOK")),
        ("SMTP_Server", settings.get("smtp_server")),
        ("SMTP_Port", settings.get("smtp_port", 25)),
        ("SMTP_Timeout_Seconds", settings.get("smtp_timeout_seconds", 30)),
        (
            "Save_SMTP_Copy_To_Sent",
            _boolean(settings.get("save_smtp_copy_to_sent", 1)),
        ),
        ("Processed_Folder", settings.get("processed_folder", "Deleted Items")),
        (
            "Auto_Reply_Enabled",
            _boolean(settings.get("auto_reply_enabled", 0)),
        ),
        ("Send_Mode", settings.get("send_mode", "DRAFT")),
        ("Resubmit_Deadline", settings.get("resubmit_deadline")),
        ("TXT_Max_Lines", settings.get("txt_max_lines", 10000)),
        (
            "Module_Display_Name",
            settings.get("module_display_name", "Outlook Revisi"),
        ),
        ("Output_Root", global_row.get("output_root")),
        ("Payroll_Period", payroll_period),
        ("PIC_HR_Emails", recipient_values["TO"]),
        ("SPV_PIC_HR_Emails", recipient_values["CC"]),
    )
    _key_value_sheet(workbook.create_sheet("General"), general_values)

    senders = configuration["outlook_sender_master"]
    sender_headers = (
        "Company",
        "Branch_Code",
        "Nik_Sender",
        "Sender_Name",
        "Sender_Email",
        "Nik_Spv",
        "Name_SPV",
        "Required_CC_Email",
        "Active",
    )
    for workflow, sheet_name in (
        ("HO", "HO_Sender_Master"),
        ("BRANCH", "Branch_Sender_Master"),
    ):
        rows = (
            (
                row["company_code"],
                row["branch_code"],
                row["sender_nik"],
                row["sender_name"],
                row["sender_email"],
                row["supervisor_nik"],
                row["supervisor_name"],
                row["required_cc_email"],
                _boolean(row["is_active"]),
            )
            for row in senders
            if row["workflow"] == workflow
        )
        _table_sheet(
            workbook.create_sheet(sheet_name),
            sender_headers,
            tuple(rows),
        )

    _table_sheet(
        workbook.create_sheet("Subject_Rules"),
        ("Workflow", "Subject_Pattern", "Active"),
        tuple(
            (
                row["workflow"],
                row["subject_pattern"],
                _boolean(row["is_active"]),
            )
            for row in configuration["outlook_subject_rules"]
        ),
    )
    _table_sheet(
        workbook.create_sheet("Attachment_Rules"),
        ("Workflow", "Allowed_Extensions", "Active"),
        tuple(
            (
                row["workflow"],
                row["extension"],
                _boolean(row["is_active"]),
            )
            for row in configuration["outlook_attachment_rules"]
        ),
    )
    _table_sheet(
        workbook.create_sheet("Validation_Rules"),
        ("Rule_Code", "Workflow", "Rule_Value", "Active"),
        tuple(
            (
                row["rule_code"],
                row["workflow"],
                row["rule_value"],
                _boolean(row["is_active"]),
            )
            for row in configuration["outlook_validation_rules"]
        ),
    )
    _table_sheet(
        workbook.create_sheet("Reply_Templates"),
        (
            "Reply_Code",
            "Recipient_Type",
            "Trigger",
            "Subject_Template",
            "Body_Template",
            "Active",
        ),
        tuple(
            (
                row["reply_code"],
                row["recipient_type"],
                row["trigger_code"],
                row["subject_template"],
                row["body_template"],
                _boolean(row["is_active"]),
            )
            for row in configuration["outlook_reply_templates"]
        ),
        wrap_columns=("Body_Template",),
    )
    return _save_legacy(
        workbook,
        output,
        WorkbookIdentity.OUTLOOK_REVISI_LEGACY,
    )


def export_hris_legacy(
    database_path: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool = False,
    create_parent: bool = False,
) -> ExportResult:
    """Export the HRIS subset using text-preserving run-control IDs."""

    configuration, _ = _validated_configuration(database_path)
    output = _prepare_output_path(
        output_path,
        overwrite=overwrite,
        create_parent=create_parent,
    )
    global_row = _one(configuration["global_settings"])
    settings = _one(configuration["hris_settings"])
    workbook = Workbook()
    workbook.remove(workbook.active)
    _key_value_sheet(
        workbook.create_sheet("General"),
        (
            ("HRIS_URL", settings.get("hris_url")),
            ("Folder_Upload_Path", global_row.get("output_root")),
        ),
    )
    _table_sheet(
        workbook.create_sheet("Run_Control"),
        ("Active", "Sequence", "Workflow", "Run_Control_ID", "Description"),
        tuple(
            (
                _boolean(row["is_active"]),
                row["sequence"],
                row["workflow"],
                str(row["run_control_id"]),
                row["description"],
            )
            for row in configuration["hris_run_controls"]
        ),
        text_columns=("Run_Control_ID",),
    )
    _key_value_sheet(
        workbook.create_sheet("Browser"),
        (
            ("Browser_Channel", settings.get("browser_channel", "msedge")),
            ("Headless", _boolean(settings.get("browser_headless", 0))),
        ),
    )
    upload_values = (
        ("Start_Date", global_row.get("period_start")),
        ("End_Date", global_row.get("period_end")),
        (
            "Stop_On_First_Failure",
            _boolean(settings.get("stop_on_first_failure", 1)),
        ),
        ("Click_Profile_Path", settings.get("click_profile_path")),
        (
            "Manual_Recovery_Enabled",
            _boolean(settings.get("manual_recovery_enabled", 1)),
        ),
        (
            "Require_Profile_Match",
            _boolean(settings.get("require_profile_match", 1)),
        ),
        ("Browser_X", settings.get("browser_x", 0)),
        ("Browser_Y", settings.get("browser_y", 0)),
        ("Browser_Width", settings.get("browser_width", 1200)),
        ("Browser_Height", settings.get("browser_height", 800)),
        ("Browser_Zoom", settings.get("browser_zoom", 100)),
        (
            "Assisted_Verification_Enabled",
            _boolean(settings.get("verification_enabled", 1)),
        ),
        (
            "Verification_Wait_Seconds",
            settings.get("verification_wait_seconds", 2),
        ),
        (
            "Verification_Timeout_Seconds",
            settings.get("verification_timeout_seconds", 30),
        ),
        (
            "Verification_Poll_Seconds",
            settings.get("verification_poll_seconds", 1),
        ),
        (
            "Verification_Success_Texts",
            settings.get(
                "verification_success_texts",
                "Process Instance|Submitted|Queued",
            ),
        ),
        (
            "Verification_Failure_Texts",
            settings.get(
                "verification_failure_texts",
                "Error|Invalid|Failed",
            ),
        ),
        (
            "Manual_Verification_On_Unknown",
            _boolean(settings.get("manual_verification_on_unknown", 1)),
        ),
        (
            "Manual_Verification_On_Error",
            _boolean(settings.get("manual_verification_on_error", 1)),
        ),
    )
    _key_value_sheet(workbook.create_sheet("Upload"), upload_values)
    _table_sheet(
        workbook.create_sheet("Reference"),
        ("Key", "Value"),
        (),
    )
    _table_sheet(
        workbook.create_sheet("Assisted_Steps"),
        (
            "Active",
            "Sequence",
            "Step_Name",
            "Action",
            "Input_Source",
            "Method",
            "Required",
            "Wait_After_Seconds",
            "Description",
        ),
        tuple(
            (
                _boolean(row["is_active"]),
                row["sequence"],
                row["step_name"],
                row["action"],
                row["input_source"],
                row["method"],
                _boolean(row["is_required"]),
                row["wait_after_seconds"],
                row["description"],
            )
            for row in configuration["hris_assisted_steps"]
        ),
    )
    return _save_legacy(
        workbook,
        output,
        WorkbookIdentity.HRIS_LEGACY,
    )


def _validated_configuration(
    database_path: str | Path,
) -> tuple[dict[str, tuple[dict[str, Any], ...]], dict[str, Any]]:
    database = Path(database_path).expanduser().resolve()
    DatabaseValidator().validate_or_raise(database)
    return _read_configuration(database)


def _one(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    if len(rows) != 1:
        raise LegacyExportUnsupportedError(
            "Legacy export requires each singleton configuration row."
        )
    return rows[0]


def _key_value_sheet(
    sheet: object,
    values: tuple[tuple[str, Any], ...],
) -> None:
    headers = ("Parameter", "Value", "Description")
    style_headers(sheet, headers, row=1)
    style_data_area(
        sheet,
        first_row=2,
        last_row=max(2, 1 + len(values)),
        last_column=3,
    )
    for row_number, (key, value) in enumerate(values, start=2):
        sheet.cell(row_number, 1, key)
        sheet.cell(row_number, 2, value)
    set_column_widths(sheet, headers)
    sheet.column_dimensions["A"].width = 38
    sheet.column_dimensions["B"].width = 55
    sheet.column_dimensions["C"].width = 32
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:C{max(1, 1 + len(values))}"


def _table_sheet(
    sheet: object,
    headers: tuple[str, ...],
    rows: tuple[tuple[Any, ...], ...],
    *,
    text_columns: tuple[str, ...] = (),
    wrap_columns: tuple[str, ...] = (),
) -> None:
    style_headers(sheet, headers, row=1)
    style_data_area(
        sheet,
        first_row=2,
        last_row=max(2, 1 + len(rows)),
        last_column=len(headers),
    )
    for row_number, row in enumerate(rows, start=2):
        for column_number, value in enumerate(row, start=1):
            cell = sheet.cell(row_number, column_number, value)
            header = headers[column_number - 1]
            if header in text_columns:
                cell.number_format = "@"
            if header in wrap_columns:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    for header in text_columns:
        column = headers.index(header) + 1
        for row_number in range(2, max(3, 2 + len(rows))):
            sheet.cell(row_number, column).number_format = "@"
    set_column_widths(sheet, headers)
    sheet.freeze_panes = "A2"
    last_column = _column_letter(len(headers))
    sheet.auto_filter.ref = (
        f"A1:{last_column}{max(1, 1 + len(rows))}"
    )


def _save_legacy(
    workbook: Workbook,
    output: Path,
    expected_identity: WorkbookIdentity,
) -> ExportResult:
    exported_at = current_timestamp()
    try:
        workbook.save(output)
    except Exception as exc:
        raise ConfigExportError(f"Unable to save legacy workbook: {exc}") from exc
    finally:
        workbook.close()
    validation = _validate_legacy(output, expected_identity)
    if not validation.is_valid:
        raise ConfigExportError(
            "Legacy workbook validation failed: "
            + "; ".join(validation.errors)
        )
    return ExportResult(
        output_path=output,
        workbook_identity=expected_identity,
        sheet_names=validation.sheet_names,
        validation=validation,
        exported_at=exported_at,
    )


def _validate_legacy(
    path: Path,
    expected_identity: WorkbookIdentity,
) -> WorkbookValidationResult:
    errors: list[str] = []
    formulas = 0
    links = 0
    has_macros = False
    workbook = load_workbook(path, data_only=False, keep_links=False)
    try:
        sheet_names = tuple(workbook.sheetnames)
        has_macros = workbook.vba_archive is not None
        links = len(getattr(workbook, "_external_links", ()))
        formulas = sum(
            cell.data_type == "f"
            for sheet in workbook.worksheets
            for row in sheet.iter_rows()
            for cell in row
        )
    finally:
        workbook.close()
    if has_macros:
        errors.append("Macros are not permitted.")
    if links:
        errors.append("External links are not permitted.")
    if formulas:
        errors.append("Formulas are not permitted.")
    detected = detect_workbook(path).identity
    if detected is not expected_identity:
        errors.append(
            f"Expected {expected_identity}, detector returned {detected}."
        )
    return WorkbookValidationResult(
        path=path,
        is_valid=not errors,
        sheet_names=sheet_names,
        formula_count=formulas,
        external_link_count=links,
        has_macros=has_macros,
        errors=tuple(errors),
    )


def _boolean(value: Any) -> str:
    return "TRUE" if bool(value) else "FALSE"


def _column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
