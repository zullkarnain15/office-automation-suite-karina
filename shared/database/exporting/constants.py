"""Stable workbook contract for OAS-K configuration exports."""

from __future__ import annotations

from dataclasses import dataclass

TEMPLATE_VERSION = "1.0"
MAX_TEMPLATE_ROWS = 500
TITLE_ROW = 1
NOTE_ROW = 2
HEADER_ROW = 3
DATA_START_ROW = 4

SHEET_ORDER = (
    "Guide",
    "Global_Settings",
    "Attendance_Settings",
    "Attendance_Sources",
    "Outlook_Settings",
    "Outlook_HO_Senders",
    "Outlook_Branch_Senders",
    "Outlook_Subject_Rules",
    "Outlook_Attachment_Rules",
    "Outlook_Validation_Rules",
    "Outlook_Reply_Templates",
    "Outlook_Summary_Recipients",
    "HRIS_Settings",
    "HRIS_Run_Controls",
    "HRIS_Assisted_Steps",
    "Comparison_Settings",
    "Attachment_Consolidation",
    "Att_Data_Repair",
)

SETTING_HEADERS = (
    "setting_key",
    "setting_value",
    "required",
    "description",
)


@dataclass(frozen=True, slots=True)
class SettingDefinition:
    key: str
    default: object
    required: bool
    description: str
    value_type: str = "TEXT"


@dataclass(frozen=True, slots=True)
class SheetDefinition:
    title: str
    note: str
    headers: tuple[str, ...]
    table: str | None
    settings: tuple[SettingDefinition, ...] = ()


SETTING_DEFINITIONS: dict[str, tuple[SettingDefinition, ...]] = {
    "Global_Settings": (
        SettingDefinition(
            "output_root",
            "",
            True,
            "Folder keluaran bersama. Isi dengan path operasional, bukan path developer.",
            "PATH",
        ),
        SettingDefinition(
            "period_start",
            "",
            False,
            "Tanggal awal periode global (YYYY-MM-DD).",
            "DATE",
        ),
        SettingDefinition(
            "period_end",
            "",
            False,
            "Tanggal akhir periode global (YYYY-MM-DD).",
            "DATE",
        ),
    ),
    "Attendance_Settings": (
        SettingDefinition("use_global_output", True, True, "Gunakan output_root global.", "BOOLEAN"),
        SettingDefinition("use_global_period", True, True, "Gunakan periode global.", "BOOLEAN"),
        SettingDefinition("split_txt_rows", 10000, True, "Maksimum baris per file TXT.", "INTEGER"),
        SettingDefinition("generate_report_default", False, True, "Buat laporan secara default.", "BOOLEAN"),
        SettingDefinition("default_workflow", "HO", True, "Workflow awal: HO atau BRANCH.", "WORKFLOW"),
    ),
    "Outlook_Settings": (
        SettingDefinition("use_global_output", True, True, "Gunakan output_root global.", "BOOLEAN"),
        SettingDefinition("use_global_period", True, True, "Gunakan periode global.", "BOOLEAN"),
        SettingDefinition("integration_method", "OOM_COM", True, "Metode integrasi Outlook yang didukung."),
        SettingDefinition("mailbox_smtp", "", True, "Alamat mailbox Outlook operasional."),
        SettingDefinition("source_folder", "Inbox", True, "Folder sumber pesan Outlook."),
        SettingDefinition("reply_from_smtp", "", False, "Alamat pengirim balasan untuk transport SMTP."),
        SettingDefinition("send_transport", "OUTLOOK", True, "Transport pengiriman: OUTLOOK atau SMTP."),
        SettingDefinition("smtp_server", "", False, "Server SMTP; wajib hanya bila transport SMTP."),
        SettingDefinition("smtp_port", 25, True, "Port SMTP.", "INTEGER"),
        SettingDefinition("smtp_timeout_seconds", 30, True, "Timeout SMTP dalam detik.", "INTEGER"),
        SettingDefinition("save_smtp_copy_to_sent", True, True, "Simpan salinan SMTP ke Sent.", "BOOLEAN"),
        SettingDefinition("processed_folder", "Deleted Items", True, "Folder pesan setelah diproses."),
        SettingDefinition("auto_reply_enabled", False, True, "Balasan otomatis; default aman adalah FALSE.", "BOOLEAN"),
        SettingDefinition("send_mode", "DRAFT", True, "Mode aman DRAFT atau mode SEND."),
        SettingDefinition("resubmit_deadline", "", False, "Batas waktu resubmit, bila digunakan."),
        SettingDefinition("txt_max_lines", 10000, True, "Maksimum baris TXT.", "INTEGER"),
        SettingDefinition("module_display_name", "Outlook Revisi", True, "Nama modul yang ditampilkan."),
        SettingDefinition(
            "payroll_period",
            "",
            True,
            "Periode subject Outlook dalam format MM-YYYY, contoh 07-2026.",
            "TEXT",
        ),
    ),
    "HRIS_Settings": (
        SettingDefinition("use_global_output", True, True, "Gunakan output_root global.", "BOOLEAN"),
        SettingDefinition("use_global_period", True, True, "Gunakan periode global.", "BOOLEAN"),
        SettingDefinition("hris_url", "", True, "URL HRIS operasional; jangan isi localhost/mock."),
        SettingDefinition("browser_channel", "msedge", True, "Channel browser."),
        SettingDefinition("browser_headless", False, True, "Jalankan browser headless.", "BOOLEAN"),
        SettingDefinition("stop_on_first_failure", True, True, "Berhenti pada kegagalan pertama.", "BOOLEAN"),
        SettingDefinition("click_profile_path", "", False, "Path profil klik opsional.", "PATH"),
        SettingDefinition("manual_recovery_enabled", True, True, "Izinkan pemulihan manual.", "BOOLEAN"),
        SettingDefinition("require_profile_match", True, True, "Wajib cocok dengan profil.", "BOOLEAN"),
        SettingDefinition("browser_x", 0, True, "Koordinat X browser.", "INTEGER"),
        SettingDefinition("browser_y", 0, True, "Koordinat Y browser.", "INTEGER"),
        SettingDefinition("browser_width", 1200, True, "Lebar browser.", "INTEGER"),
        SettingDefinition("browser_height", 800, True, "Tinggi browser.", "INTEGER"),
        SettingDefinition("browser_zoom", 100, True, "Zoom browser dalam persen.", "INTEGER"),
        SettingDefinition("verification_enabled", True, True, "Aktifkan verifikasi assisted.", "BOOLEAN"),
        SettingDefinition("verification_wait_seconds", 2.0, True, "Waktu tunggu awal verifikasi.", "REAL"),
        SettingDefinition("verification_timeout_seconds", 30.0, True, "Timeout verifikasi.", "REAL"),
        SettingDefinition("verification_poll_seconds", 1.0, True, "Interval polling verifikasi.", "REAL"),
        SettingDefinition("verification_success_texts", "Process Instance|Submitted|Queued", True, "Teks keberhasilan, dipisahkan tanda |."),
        SettingDefinition("verification_failure_texts", "Error|Invalid|Failed", True, "Teks kegagalan, dipisahkan tanda |."),
        SettingDefinition("manual_verification_on_unknown", True, True, "Verifikasi manual bila status tidak diketahui.", "BOOLEAN"),
        SettingDefinition("manual_verification_on_error", True, True, "Verifikasi manual bila terjadi error.", "BOOLEAN"),
    ),
    "Comparison_Settings": (
        SettingDefinition("use_global_output", True, True, "Gunakan output_root global.", "BOOLEAN"),
        SettingDefinition("use_global_period", True, True, "Gunakan periode global.", "BOOLEAN"),
    ),
    "Attachment_Consolidation": (
        SettingDefinition("use_global_output", True, True, "Gunakan output_root global.", "BOOLEAN"),
        SettingDefinition("txt_max_lines", 10000, True, "Maksimum baris TXT hasil konsolidasi.", "INTEGER"),
    ),
    "Att_Data_Repair": (
        SettingDefinition("enabled", True, True, "Aktifkan modul Att Data Repair.", "BOOLEAN"),
        SettingDefinition("minimum_duration_minutes", 61, True, "Durasi minimum repair dalam menit.", "INTEGER"),
        SettingDefinition("weekday_default_in", "09:30", True, "Jam masuk default Senin-Jumat.", "TIME"),
        SettingDefinition("weekday_default_out", "17:00", True, "Jam keluar default Senin-Jumat.", "TIME"),
        SettingDefinition("saturday_default_in", "09:30", True, "Jam masuk default Sabtu.", "TIME"),
        SettingDefinition("saturday_default_out", "12:05", True, "Jam keluar default Sabtu.", "TIME"),
        SettingDefinition("saturday_missing_out_default", "11:00", True, "Jam keluar saat Time_Out Sabtu kosong.", "TIME"),
        SettingDefinition("sunday_invalid_default_in", "09:30", True, "Jam masuk default Minggu bila jam invalid.", "TIME"),
        SettingDefinition("sunday_invalid_default_out", "12:05", True, "Jam keluar default Minggu bila jam invalid.", "TIME"),
        SettingDefinition("midnight_time_out_default", "23:59", True, "Pengganti Time_Out saat nilainya 00:00.", "TIME"),
        SettingDefinition("txt_max_rows", 10000, True, "Maksimum baris per TXT Att Data Repair.", "INTEGER"),
        SettingDefinition("generate_txt", True, True, "Buat TXT HRIS.", "BOOLEAN"),
        SettingDefinition("generate_excel_report", True, True, "Buat Excel report audit.", "BOOLEAN"),
        SettingDefinition("use_global_period", True, True, "Gunakan periode global bila UI mendukung.", "BOOLEAN"),
        SettingDefinition("use_global_output", True, True, "Gunakan output root global bila UI mendukung.", "BOOLEAN"),
    ),
}

DATA_HEADERS: dict[str, tuple[str, ...]] = {
    "Attendance_Sources": (
        "workflow", "source_code", "source_name", "mdb_path", "is_active", "sort_order"
    ),
    "Outlook_HO_Senders": (
        "company_code", "branch_code", "sender_nik", "sender_name",
        "sender_email", "supervisor_nik", "supervisor_name", "required_cc_email",
        "is_active",
    ),
    "Outlook_Branch_Senders": (
        "company_code", "branch_code", "sender_nik", "sender_name",
        "sender_email", "supervisor_nik", "supervisor_name", "required_cc_email",
        "is_active",
    ),
    "Outlook_Subject_Rules": ("workflow", "subject_pattern", "is_active"),
    "Outlook_Attachment_Rules": ("workflow", "extension", "is_active"),
    "Outlook_Validation_Rules": ("rule_code", "workflow", "rule_value", "is_active"),
    "Outlook_Reply_Templates": (
        "reply_code", "recipient_type", "trigger_code", "subject_template",
        "body_template", "is_active",
    ),
    "Outlook_Summary_Recipients": (
        "recipient_type", "email_address", "is_active", "sort_order"
    ),
    "HRIS_Run_Controls": (
        "workflow", "sequence", "run_control_id", "description", "is_active"
    ),
    "HRIS_Assisted_Steps": (
        "sequence", "step_name", "action", "input_source", "method",
        "is_required", "wait_after_seconds", "description", "is_active",
    ),
}

SHEET_TABLES = {
    "Global_Settings": "global_settings",
    "Attendance_Settings": "attendance_settings",
    "Attendance_Sources": "attendance_sources",
    "Outlook_Settings": "outlook_settings",
    "Outlook_HO_Senders": "outlook_sender_master",
    "Outlook_Branch_Senders": "outlook_sender_master",
    "Outlook_Subject_Rules": "outlook_subject_rules",
    "Outlook_Attachment_Rules": "outlook_attachment_rules",
    "Outlook_Validation_Rules": "outlook_validation_rules",
    "Outlook_Reply_Templates": "outlook_reply_templates",
    "Outlook_Summary_Recipients": "outlook_summary_recipients",
    "HRIS_Settings": "hris_settings",
    "HRIS_Run_Controls": "hris_run_controls",
    "HRIS_Assisted_Steps": "hris_assisted_steps",
    "Comparison_Settings": "comparison_settings",
    "Attachment_Consolidation": "attachment_consolidation_settings",
    "Att_Data_Repair": "att_data_repair_settings",
}

BOOLEAN_COLUMNS = {"is_active", "is_required"}
WORKFLOW_COLUMNS = {"workflow"}
