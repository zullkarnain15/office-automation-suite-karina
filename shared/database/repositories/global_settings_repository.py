"""Repository for the global output root and optional period."""

from __future__ import annotations

import sqlite3

from shared.database.exceptions import RepositoryError
from shared.database.models import GlobalSettings
from shared.database.time_utils import current_timestamp, validate_date_pair


class GlobalSettingsRepository:
    """Read and save the single active global settings row."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_global_settings(self) -> GlobalSettings | None:
        """Return global settings, or None before first configuration."""

        try:
            row = self.connection.execute(
                """
                SELECT
                    global_settings_id,
                    output_root,
                    period_start,
                    period_end,
                    updated_at,
                    updated_by
                FROM global_settings
                WHERE global_settings_id = 1
                """
            ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to read global settings: {exc}"
            ) from exc

        return GlobalSettings(**dict(row)) if row is not None else None

    def save_global_settings(
        self,
        *,
        output_root: str,
        period_start: str | None = None,
        period_end: str | None = None,
        updated_at: str | None = None,
        updated_by: str | None = None,
    ) -> GlobalSettings:
        """Upsert global values without creating the output directory."""

        normalized_output = output_root.strip()
        if not normalized_output:
            raise ValueError("output_root must not be empty.")
        validate_date_pair(period_start, period_end)
        timestamp = updated_at or current_timestamp()

        try:
            self.connection.execute(
                """
                INSERT INTO global_settings (
                    global_settings_id,
                    output_root,
                    period_start,
                    period_end,
                    updated_at,
                    updated_by
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(global_settings_id) DO UPDATE SET
                    output_root = excluded.output_root,
                    period_start = excluded.period_start,
                    period_end = excluded.period_end,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    normalized_output,
                    period_start,
                    period_end,
                    timestamp,
                    updated_by,
                ),
            )
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to save global settings: {exc}"
            ) from exc

        return GlobalSettings(
            output_root=normalized_output,
            period_start=period_start,
            period_end=period_end,
            updated_at=timestamp,
            updated_by=updated_by,
        )
