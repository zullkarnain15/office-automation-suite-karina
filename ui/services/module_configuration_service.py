"""Read-only facade for active module configuration summaries and details."""

from __future__ import annotations

from pathlib import Path

from shared.database import DatabaseValidator, SQLiteConnectionFactory
from ui.configuration_ux_models import (
    ActiveConfigurationStatus,
    ModuleConfigurationDetail,
    ModuleConfigurationSummary,
)

_SOURCE = "OAS-K Database"
_MODULES = ("ATTENDANCE", "OUTLOOK_REVISI", "HRIS", "UTILITIES")


class ModuleConfigurationService:
    def __init__(self, factory=None, validator=None) -> None:
        self.factory = factory or SQLiteConnectionFactory()
        self.validator = validator or DatabaseValidator(self.factory)

    def load_summaries(
        self, database_path: Path | None
    ) -> tuple[ModuleConfigurationSummary, ...]:
        if database_path is None or not self.validator.validate(database_path).is_valid:
            return tuple(self._unavailable(module) for module in _MODULES)
        with self.factory.connect(database_path, read_only=True) as connection:
            return (
                self._attendance_summary(connection),
                self._outlook_summary(connection),
                self._hris_summary(connection),
                self._utilities_summary(connection),
            )

    def load_detail(
        self, database_path: Path, module: str
    ) -> ModuleConfigurationDetail:
        if module not in _MODULES:
            raise ValueError(f"Module configuration tidak dikenal: {module}")
        self.validator.validate_or_raise(database_path)
        with self.factory.connect(database_path, read_only=True) as connection:
            if module == "ATTENDANCE":
                sections = (
                    ("Pengaturan", self._rows(connection, "attendance_settings")),
                    (
                        "Sumber Aktif",
                        self._rows(
                            connection,
                            "attendance_sources",
                            "WHERE is_active = 1 ORDER BY workflow, sort_order",
                        ),
                    ),
                )
                title = "Attendance"
            elif module == "OUTLOOK_REVISI":
                sections = tuple(
                    (label, self._rows(connection, table, clause))
                    for label, table, clause in (
                        ("Pengaturan", "outlook_settings", ""),
                        ("Sender Aktif", "outlook_sender_master", "WHERE is_active=1"),
                        ("Subject Rules", "outlook_subject_rules", "WHERE is_active=1"),
                        ("Attachment Rules", "outlook_attachment_rules", "WHERE is_active=1"),
                        ("Validation Rules", "outlook_validation_rules", "WHERE is_active=1"),
                        ("Reply Templates", "outlook_reply_templates", "WHERE is_active=1"),
                        ("Recipients", "outlook_summary_recipients", "WHERE is_active=1"),
                    )
                )
                title = "Outlook Revisi"
            elif module == "HRIS":
                sections = (
                    ("Pengaturan", self._rows(connection, "hris_settings")),
                    ("Run Controls", self._rows(connection, "hris_run_controls", "WHERE is_active=1 ORDER BY workflow, sequence")),
                    ("Assisted Steps", self._rows(connection, "hris_assisted_steps", "WHERE is_active=1 ORDER BY sequence")),
                    ("Recorder Profile", self._profile_rows(connection)),
                )
                title = "HRIS"
            else:
                sections = (
                    ("Comparison Result", self._rows(connection, "comparison_settings")),
                    ("Attachment Consolidation", self._rows(connection, "attachment_consolidation_settings")),
                    ("Att Data Repair", self._safe_rows(connection, "att_data_repair_settings")),
                )
                title = "Utilities"
        return ModuleConfigurationDetail(module, title, sections)

    @staticmethod
    def _rows(connection, table: str, clause: str = "") -> tuple[dict, ...]:
        rows = connection.execute(f'SELECT * FROM "{table}" {clause}').fetchall()
        return tuple(dict(row) for row in rows)

    @classmethod
    def _safe_rows(cls, connection, table: str, clause: str = "") -> tuple[dict, ...]:
        if not cls._table_exists(connection, table):
            return ()
        return cls._rows(connection, table, clause)

    @staticmethod
    def _table_exists(connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _profile_rows(connection) -> tuple[dict, ...]:
        row = connection.execute(
            "SELECT click_profile_path, require_profile_match FROM hris_settings LIMIT 1"
        ).fetchone()
        return (dict(row),) if row else ()

    @staticmethod
    def _count(connection, table: str, where: str = "") -> int:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0])

    def _attendance_summary(self, connection) -> ModuleConfigurationSummary:
        settings = connection.execute("SELECT * FROM attendance_settings LIMIT 1").fetchone()
        if settings is None:
            return self._missing("ATTENDANCE", "Attendance")
        ho = self._count(connection, "attendance_sources", "WHERE workflow='HO' AND is_active=1")
        branch = self._count(connection, "attendance_sources", "WHERE workflow='BRANCH' AND is_active=1")
        status = ActiveConfigurationStatus.ACTIVE if ho or branch else ActiveConfigurationStatus.WARNING
        return ModuleConfigurationSummary(
            "ATTENDANCE", "Attendance", status, _SOURCE,
            (("HO Sources", f"{ho} aktif"), ("Branch Sources", f"{branch} aktif"), ("Batas Baris TXT", f"{settings['split_txt_rows']:,}".replace(",", "."))),
            settings["updated_at"],
            None if ho or branch else "Belum ada sumber Attendance aktif.",
        )

    def _outlook_summary(self, connection) -> ModuleConfigurationSummary:
        settings = connection.execute("SELECT * FROM outlook_settings LIMIT 1").fetchone()
        if settings is None:
            return self._missing("OUTLOOK_REVISI", "Outlook Revisi")
        senders = self._count(
            connection, "outlook_sender_master", "WHERE is_active=1"
        )
        rules = sum(self._count(connection, table, "WHERE is_active=1") for table in ("outlook_subject_rules", "outlook_attachment_rules", "outlook_validation_rules"))
        templates = self._count(
            connection, "outlook_reply_templates", "WHERE is_active=1"
        )
        risky = bool(settings["auto_reply_enabled"]) or settings["send_mode"] == "SEND"
        locked_target = (
            str(settings["mailbox_smtp"]).casefold() == "karina.hr.1@oto.co.id"
            and str(settings["source_folder"]).casefold() == "inbox"
        )
        payroll_period = str(settings["payroll_period"] or "").strip()
        complete = bool(senders and rules and templates and payroll_period)
        status = (
            ActiveConfigurationStatus.INVALID
            if not locked_target
            else ActiveConfigurationStatus.NOT_CONFIGURED
            if not complete
            else ActiveConfigurationStatus.WARNING
            if risky
            else ActiveConfigurationStatus.ACTIVE
        )
        warning = (
            "Mailbox atau folder tidak sesuai kontrak yang dikunci."
            if not locked_target
            else "Payroll Period Outlook belum diisi."
            if not payroll_period
            else "Sender, rules, atau template aktif belum lengkap."
            if not complete
            else "Pengiriman email otomatis aktif; periksa sebelum menjalankan."
            if risky
            else None
        )
        return ModuleConfigurationSummary(
            "OUTLOOK_REVISI", "Outlook Revisi", status, _SOURCE,
            (("Mailbox", settings["mailbox_smtp"]), ("Folder", settings["source_folder"]), ("Payroll Period", payroll_period or "-"), ("Sender Aktif", str(senders)), ("Rules Aktif", str(rules)), ("Send Mode", settings["send_mode"]), ("Auto Reply", "Aktif" if settings["auto_reply_enabled"] else "Nonaktif")),
            settings["updated_at"],
            warning,
        )

    def _hris_summary(self, connection) -> ModuleConfigurationSummary:
        settings = connection.execute("SELECT * FROM hris_settings LIMIT 1").fetchone()
        if settings is None:
            return self._missing("HRIS", "HRIS")
        ho = self._count(connection, "hris_run_controls", "WHERE workflow='HO' AND is_active=1")
        branch = self._count(connection, "hris_run_controls", "WHERE workflow='BRANCH' AND is_active=1")
        steps = self._count(connection, "hris_assisted_steps", "WHERE is_active=1")
        profile = bool(str(settings["click_profile_path"] or "").strip())
        return ModuleConfigurationSummary(
            "HRIS", "HRIS", ActiveConfigurationStatus.ACTIVE, _SOURCE,
            (("HO Run Controls", f"{ho} aktif"), ("Branch Run Controls", f"{branch} aktif"), ("Assisted Steps", f"{steps} aktif"), ("Recorder Profile", "Tersedia" if profile else "Belum dipilih")),
            settings["updated_at"],
        )

    def _utilities_summary(self, connection) -> ModuleConfigurationSummary:
        comparison = connection.execute("SELECT * FROM comparison_settings LIMIT 1").fetchone()
        attachment = connection.execute("SELECT * FROM attachment_consolidation_settings LIMIT 1").fetchone()
        att_data_repair = (
            connection.execute("SELECT * FROM att_data_repair_settings LIMIT 1").fetchone()
            if self._table_exists(connection, "att_data_repair_settings")
            else None
        )
        if comparison is None and attachment is None and att_data_repair is None:
            return self._missing("UTILITIES", "Utilities")
        updated = max(
            str(row["updated_at"])
            for row in (comparison, attachment, att_data_repair)
            if row
        )
        return ModuleConfigurationSummary(
            "UTILITIES", "Utilities", ActiveConfigurationStatus.ACTIVE, _SOURCE,
            (
                ("Comparison Result", "Aktif" if comparison else "Belum Dikonfigurasi"),
                ("Attachment Consolidation", "Aktif" if attachment else "Belum Dikonfigurasi"),
                (
                    "Att Data Repair",
                    self._att_data_repair_status(att_data_repair),
                ),
                ("TXT Max Lines", str(attachment["txt_max_lines"]) if attachment else "-"),
                (
                    "Att Data Repair TXT Max Rows",
                    str(att_data_repair["txt_max_rows"]) if att_data_repair else "-",
                ),
            ),
            updated,
        )

    @staticmethod
    def _att_data_repair_status(row) -> str:
        if row is None:
            return "Belum Dikonfigurasi"
        return "Aktif" if row["enabled"] else "Nonaktif"

    @staticmethod
    def _missing(module: str, title: str) -> ModuleConfigurationSummary:
        return ModuleConfigurationSummary(module, title, ActiveConfigurationStatus.NOT_CONFIGURED, _SOURCE, (), None)

    @staticmethod
    def _unavailable(module: str) -> ModuleConfigurationSummary:
        title = {"ATTENDANCE": "Attendance", "OUTLOOK_REVISI": "Outlook Revisi", "HRIS": "HRIS", "UTILITIES": "Utilities"}[module]
        return ModuleConfigurationSummary(module, title, ActiveConfigurationStatus.UNAVAILABLE, _SOURCE, (), None, "Database aktif belum tersedia.")
