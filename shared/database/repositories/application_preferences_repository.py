"""Repository for local, non-template application preferences."""

from __future__ import annotations

import sqlite3

from shared.database.exceptions import RepositoryError
from shared.database.time_utils import current_timestamp


class ApplicationPreferencesRepository:
    """Read and upsert values in the existing generic preference table."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_text_values(self, keys: tuple[str, ...]) -> dict[str, str]:
        if not keys:
            return {}
        placeholders = ", ".join("?" for _ in keys)
        try:
            rows = self.connection.execute(
                f"SELECT preference_key, preference_value "
                f"FROM application_preferences "
                f"WHERE preference_key IN ({placeholders})",
                keys,
            ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to read application preferences: {exc}"
            ) from exc
        return {
            str(row["preference_key"]): str(row["preference_value"])
            for row in rows
        }

    def save_text_values(self, values: dict[str, str]) -> None:
        timestamp = current_timestamp()
        try:
            for key, value in values.items():
                self.connection.execute(
                    """
                    INSERT INTO application_preferences (
                        preference_key, preference_value, value_type, updated_at
                    ) VALUES (?, ?, 'TEXT', ?)
                    ON CONFLICT(preference_key) DO UPDATE SET
                        preference_value = excluded.preference_value,
                        value_type = excluded.value_type,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, timestamp),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to save application preferences: {exc}"
            ) from exc
