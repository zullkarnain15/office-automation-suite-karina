"""Lightweight Utilities landing data and read-only SQLite defaults."""

from __future__ import annotations

from pathlib import Path

from shared.database import SQLiteConnectionFactory
from shared.database.repositories import GlobalSettingsRepository
from ui.utilities_models import UtilitiesDefaults, UtilitiesFeature, UtilitiesFeatureSummary


class UtilitiesService:
    def __init__(self, storage_service, factory: SQLiteConnectionFactory | None = None) -> None:
        self.storage_service = storage_service
        self.factory = factory or SQLiteConnectionFactory()

    def landing_summaries(self) -> tuple[UtilitiesFeatureSummary, ...]:
        return (
            UtilitiesFeatureSummary(
                UtilitiesFeature.COMPARISON_RESULT,
                "Comparison Result",
                "Bandingkan report Attendance dan Outlook Revisi secara terkontrol.",
                "Ready",
            ),
            UtilitiesFeatureSummary(
                UtilitiesFeature.ATTACHMENT_CONSOLIDATION,
                "Attachment Consolidation",
                "Konsolidasikan attachment Excel atau TXT ke output HRIS terstruktur.",
                "Ready",
            ),
            UtilitiesFeatureSummary(
                UtilitiesFeature.ATT_DATA_REPAIR,
                "Att Data Repair",
                (
                    "Periksa dan perbaiki data kehadiran dari report Attachment "
                    "Consolidation, lalu hasilkan TXT HRIS dan Excel audit report."
                ),
                "Ready",
            ),
        )

    def load_defaults(self) -> UtilitiesDefaults:
        status = self.storage_service.resolve_status()
        database = status.database_path
        if not status.database_valid or database is None:
            return UtilitiesDefaults(
                database_available=False,
                database_path=database,
                data_root=status.data_root,
                warning="Data Location belum siap. Atur melalui Settings.",
            )
        with self.factory.connect(database, read_only=True) as connection:
            global_value = GlobalSettingsRepository(connection).get_global_settings()
            comparison = connection.execute(
                "SELECT use_global_output, use_global_period, updated_at "
                "FROM comparison_settings WHERE comparison_settings_id = 1"
            ).fetchone()
            attachment = connection.execute(
                "SELECT use_global_output, txt_max_lines, updated_at "
                "FROM attachment_consolidation_settings "
                "WHERE attachment_settings_id = 1"
            ).fetchone()
            att_data_repair = connection.execute(
                """
                SELECT
                    enabled,
                    use_global_output,
                    use_global_period,
                    generate_txt,
                    generate_excel_report,
                    txt_max_rows,
                    updated_at
                FROM att_data_repair_settings
                WHERE att_data_repair_settings_id = 1
                """
            ).fetchone()
        return UtilitiesDefaults(
            database_available=True,
            database_path=database,
            data_root=status.data_root,
            output_root=Path(global_value.output_root)
            if global_value and global_value.output_root
            else None,
            period_start=global_value.period_start if global_value else None,
            period_end=global_value.period_end if global_value else None,
            comparison_use_global_output=bool(comparison["use_global_output"])
            if comparison
            else True,
            comparison_use_global_period=bool(comparison["use_global_period"])
            if comparison
            else True,
            comparison_updated_at=comparison["updated_at"] if comparison else None,
            attachment_use_global_output=bool(attachment["use_global_output"])
            if attachment
            else True,
            attachment_txt_max_lines=int(attachment["txt_max_lines"])
            if attachment
            else 10000,
            attachment_updated_at=attachment["updated_at"] if attachment else None,
            att_data_repair_enabled=bool(att_data_repair["enabled"])
            if att_data_repair
            else True,
            att_data_repair_use_global_output=bool(att_data_repair["use_global_output"])
            if att_data_repair
            else True,
            att_data_repair_use_global_period=bool(att_data_repair["use_global_period"])
            if att_data_repair
            else True,
            att_data_repair_generate_txt=bool(att_data_repair["generate_txt"])
            if att_data_repair
            else True,
            att_data_repair_generate_excel_report=bool(
                att_data_repair["generate_excel_report"]
            )
            if att_data_repair
            else True,
            att_data_repair_txt_max_rows=int(att_data_repair["txt_max_rows"])
            if att_data_repair
            else 10000,
            att_data_repair_updated_at=att_data_repair["updated_at"]
            if att_data_repair
            else None,
        )
