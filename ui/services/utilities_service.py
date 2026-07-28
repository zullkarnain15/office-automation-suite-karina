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
        )

    def load_defaults(self) -> UtilitiesDefaults:
        status = self.storage_service.resolve_status()
        database = status.database_path
        if not status.database_valid or database is None:
            return UtilitiesDefaults(
                False,
                database,
                status.data_root,
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
        return UtilitiesDefaults(
            True,
            database,
            status.data_root,
            Path(global_value.output_root) if global_value and global_value.output_root else None,
            global_value.period_start if global_value else None,
            global_value.period_end if global_value else None,
            bool(comparison["use_global_output"]) if comparison else True,
            bool(comparison["use_global_period"]) if comparison else True,
            comparison["updated_at"] if comparison else None,
            bool(attachment["use_global_output"]) if attachment else True,
            int(attachment["txt_max_lines"]) if attachment else 10000,
            attachment["updated_at"] if attachment else None,
        )
