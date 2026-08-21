"""Typed access to database metadata."""

from __future__ import annotations

import sqlite3

from shared.database.exceptions import RepositoryError
from shared.database.models import DatabaseMetadata


class MetadataRepository:
    """Read the database metadata singleton."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get_metadata(self) -> DatabaseMetadata:
        """Return the required metadata row."""

        try:
            row = self.connection.execute(
                """
                SELECT
                    metadata_id,
                    database_uuid,
                    schema_version,
                    application_version,
                    created_at,
                    updated_at,
                    last_migrated_at
                FROM database_metadata
                WHERE metadata_id = 1
                """
            ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(
                f"Unable to read database metadata: {exc}"
            ) from exc

        if row is None:
            raise RepositoryError("Database metadata is missing.")
        return DatabaseMetadata(**dict(row))
