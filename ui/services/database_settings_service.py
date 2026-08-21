"""Database settings facade; widgets contain no SQL."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from shared.database import DatabaseValidator, SQLiteConnectionFactory
from shared.database.models import ConfigurationAuditRecord
from shared.database.repositories import (
    ApplicationPreferencesRepository,
    AuditRepository,
    GlobalSettingsRepository,
)
from shared.database.time_utils import current_timestamp, validate_date_pair
from shared.payroll_period import normalize_payroll_period
from ui.services.protocols import (
    GlobalSettingsDraft,
    HRISTxtSourceDraft,
    ModuleGlobalUsage,
    OutlookOperationalSettingsDraft,
)

MODULE_USAGE = (
    ("ATTENDANCE", "Attendance", "attendance_settings", True),
    ("OUTLOOK_REVISI", "Outlook Revisi", "outlook_settings", False),
    ("HRIS", "HRIS", "hris_settings", True),
    ("COMPARISON", "Comparison Result", "comparison_settings", True),
    (
        "ATTACHMENT_CONSOLIDATION",
        "Attachment Consolidation",
        "attachment_consolidation_settings",
        False,
    ),
)
HRIS_TXT_SOURCE_HO_KEY = "hris_txt_source_ho"
HRIS_TXT_SOURCE_BRANCH_KEY = "hris_txt_source_branch"


class DatabaseSettingsService:
    def __init__(
        self,
        factory: SQLiteConnectionFactory | None = None,
        validator: DatabaseValidator | None = None,
    ) -> None:
        self.factory = factory or SQLiteConnectionFactory()
        self.validator = validator or DatabaseValidator(self.factory)

    def load_global_settings(self, database_path: Path) -> GlobalSettingsDraft:
        with self.factory.connect(database_path, read_only=True) as connection:
            value = GlobalSettingsRepository(connection).get_global_settings()
        if value is None:
            return GlobalSettingsDraft()
        return GlobalSettingsDraft(
            value.output_root,
            value.period_start,
            value.period_end,
        )

    def save_global_settings(
        self,
        database_path: Path,
        draft: GlobalSettingsDraft,
        *,
        operator: str | None = None,
    ) -> GlobalSettingsDraft:
        output = draft.output_root.strip()
        if not output:
            raise ValueError("Global Output Root wajib diisi sebelum menyimpan.")
        validate_date_pair(draft.period_start, draft.period_end)
        with self.factory.connect(database_path) as connection:
            repository = GlobalSettingsRepository(connection)
            old = repository.get_global_settings()
            saved = repository.save_global_settings(
                output_root=output,
                period_start=draft.period_start,
                period_end=draft.period_end,
                updated_by=operator,
            )
            old_values = {
                "output_root": old.output_root if old else None,
                "period_start": old.period_start if old else None,
                "period_end": old.period_end if old else None,
            }
            new_values = {
                "output_root": saved.output_root,
                "period_start": saved.period_start,
                "period_end": saved.period_end,
            }
            audit = AuditRepository(connection)
            for key, new_value in new_values.items():
                if old_values[key] != new_value:
                    audit.add_audit_record(
                        ConfigurationAuditRecord(
                            changed_at=current_timestamp(),
                            module_code="GLOBAL",
                            setting_scope="GLOBAL_SETTINGS",
                            setting_key=key,
                            old_value=old_values[key],
                            new_value=new_value,
                            change_source="Unified UI",
                            operator=operator,
                        )
                    )
        return GlobalSettingsDraft(
            saved.output_root,
            saved.period_start,
            saved.period_end,
        )

    def load_hris_txt_source_preferences(
        self,
        database_path: Path,
    ) -> HRISTxtSourceDraft:
        with self.factory.connect(database_path, read_only=True) as connection:
            values = ApplicationPreferencesRepository(connection).get_text_values(
                (HRIS_TXT_SOURCE_HO_KEY, HRIS_TXT_SOURCE_BRANCH_KEY)
            )
        return HRISTxtSourceDraft(
            values.get(HRIS_TXT_SOURCE_HO_KEY, ""),
            values.get(HRIS_TXT_SOURCE_BRANCH_KEY, ""),
        )

    def save_hris_txt_source_preferences(
        self,
        database_path: Path,
        draft: HRISTxtSourceDraft,
    ) -> HRISTxtSourceDraft:
        saved = HRISTxtSourceDraft(
            self._normalize_optional_folder(draft.ho_folder, "HO"),
            self._normalize_optional_folder(draft.branch_folder, "Branch"),
        )
        with self.factory.connect(database_path) as connection:
            ApplicationPreferencesRepository(connection).save_text_values(
                {
                    HRIS_TXT_SOURCE_HO_KEY: saved.ho_folder,
                    HRIS_TXT_SOURCE_BRANCH_KEY: saved.branch_folder,
                }
            )
        return saved

    @staticmethod
    def _normalize_optional_folder(value: str, source_type: str) -> str:
        raw = value.strip()
        if not raw:
            return ""
        folder = Path(raw).expanduser()
        if not folder.is_absolute() or not folder.is_dir():
            raise ValueError(
                f"Folder HRIS TXT Source {source_type} tidak ditemukan: {raw}"
            )
        return str(folder)

    def load_outlook_operational_settings(
        self,
        database_path: Path,
    ) -> OutlookOperationalSettingsDraft:
        with self.factory.connect(database_path, read_only=True) as connection:
            row = connection.execute(
                """
                SELECT payroll_period, resubmit_deadline
                FROM outlook_settings
                WHERE outlook_settings_id = 1
                """
            ).fetchone()
        if row is None:
            return OutlookOperationalSettingsDraft()
        return OutlookOperationalSettingsDraft(
            str(row["payroll_period"] or ""),
            str(row["resubmit_deadline"] or ""),
        )

    def save_outlook_operational_settings(
        self,
        database_path: Path,
        draft: OutlookOperationalSettingsDraft,
        *,
        operator: str | None = None,
    ) -> OutlookOperationalSettingsDraft:
        payroll_period = normalize_payroll_period(draft.payroll_period)
        assert payroll_period is not None
        deadline = draft.resubmit_deadline.strip()
        timestamp = current_timestamp()
        with self.factory.connect(database_path) as connection:
            old = connection.execute(
                """
                SELECT payroll_period, resubmit_deadline
                FROM outlook_settings
                WHERE outlook_settings_id = 1
                """
            ).fetchone()
            if old is None:
                raise ValueError("Outlook Settings belum tersedia di database.")
            connection.execute(
                """
                UPDATE outlook_settings
                SET payroll_period = ?,
                    resubmit_deadline = ?,
                    updated_at = ?
                WHERE outlook_settings_id = 1
                """,
                (payroll_period, deadline or None, timestamp),
            )
            audit = AuditRepository(connection)
            for key, old_value, new_value in (
                ("payroll_period", old["payroll_period"], payroll_period),
                ("resubmit_deadline", old["resubmit_deadline"], deadline or None),
            ):
                if (old_value or "") == (new_value or ""):
                    continue
                audit.add_audit_record(
                    ConfigurationAuditRecord(
                        changed_at=timestamp,
                        module_code="OUTLOOK_REVISI",
                        setting_scope="outlook_settings",
                        setting_key=key,
                        old_value=str(old_value or ""),
                        new_value=str(new_value or ""),
                        change_source="Unified UI",
                        operator=operator,
                    )
                )
        return OutlookOperationalSettingsDraft(payroll_period, deadline)

    def load_module_global_usage(
        self,
        database_path: Path,
    ) -> tuple[ModuleGlobalUsage, ...]:
        values: list[ModuleGlobalUsage] = []
        with self.factory.connect(database_path, read_only=True) as connection:
            for module, label, table, supports_period in MODULE_USAGE:
                row = connection.execute(
                    "SELECT use_global_output"
                    + (", use_global_period" if supports_period else "")
                    + f" FROM {table} LIMIT 1"
                ).fetchone()
                values.append(
                    ModuleGlobalUsage(
                        module=module,
                        label=label,
                        use_global_output=bool(row[0]) if row else True,
                        use_global_period=(
                            bool(row[1]) if row and supports_period else None
                        ),
                        available=row is not None,
                    )
                )
        return tuple(values)

    def save_module_global_usage(
        self,
        database_path: Path,
        values: Sequence[ModuleGlobalUsage],
        *,
        operator: str | None = None,
    ) -> tuple[ModuleGlobalUsage, ...]:
        metadata = {item[0]: item for item in MODULE_USAGE}
        timestamp = current_timestamp()
        with self.factory.connect(database_path) as connection:
            audit = AuditRepository(connection)
            for value in values:
                if not value.available:
                    continue
                module, _, table, supports_period = metadata[value.module]
                old = connection.execute(
                    "SELECT use_global_output"
                    + (", use_global_period" if supports_period else "")
                    + f" FROM {table} LIMIT 1"
                ).fetchone()
                if old is None:
                    continue
                params: list[object] = [int(value.use_global_output)]
                assignments = ["use_global_output = ?"]
                if supports_period:
                    assignments.append("use_global_period = ?")
                    params.append(int(bool(value.use_global_period)))
                assignments.append("updated_at = ?")
                params.append(timestamp)
                connection.execute(
                    f"UPDATE {table} SET {', '.join(assignments)}",
                    params,
                )
                new_values = [("use_global_output", old[0], value.use_global_output)]
                if supports_period:
                    new_values.append(
                        (
                            "use_global_period",
                            old[1],
                            bool(value.use_global_period),
                        )
                    )
                for key, old_value, new_value in new_values:
                    if bool(old_value) != bool(new_value):
                        audit.add_audit_record(
                            ConfigurationAuditRecord(
                                changed_at=timestamp,
                                module_code=module,
                                setting_scope=table,
                                setting_key=key,
                                old_value=str(bool(old_value)),
                                new_value=str(bool(new_value)),
                                change_source="Unified UI",
                                operator=operator,
                            )
                        )
        return self.load_module_global_usage(database_path)

    def validate_database(self, database_path: Path):
        return self.validator.validate(database_path)

    def get_metadata(self, database_path: Path) -> dict[str, object]:
        with self.factory.connect(database_path, read_only=True) as connection:
            row = connection.execute(
                "SELECT schema_version, application_version "
                "FROM database_metadata WHERE metadata_id = 1"
            ).fetchone()
        return dict(row) if row else {}
