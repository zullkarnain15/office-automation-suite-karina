"""Typed, short-lived SQLite connection factory."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

from shared.database.constants import (
    DEFAULT_BUSY_TIMEOUT_MS,
    JOURNAL_MODE,
    SYNCHRONOUS_MODE,
)


class SQLiteConnectionFactory:
    """Open configured SQLite connections without a global singleton."""

    def __init__(
        self,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must not be negative.")
        self.busy_timeout_ms = busy_timeout_ms

    @contextmanager
    def connect(
        self,
        database_path: str | Path,
        *,
        create_parent: bool = False,
        read_only: bool = False,
    ) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection and commit or roll back safely."""

        path = Path(database_path).expanduser()
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            raise FileNotFoundError(
                f"Database parent directory does not exist: {path.parent}"
            )

        if read_only and not path.is_file():
            raise FileNotFoundError(f"Database file does not exist: {path}")

        connection: sqlite3.Connection | None = None
        try:
            connection = self._open(path, read_only=read_only)
            self._configure(connection, read_only=read_only)
            yield connection
            if connection.in_transaction:
                connection.commit()
        except BaseException:
            if connection is not None and connection.in_transaction:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _open(
        path: Path,
        *,
        read_only: bool,
    ) -> sqlite3.Connection:
        if read_only:
            normalized = path.resolve().as_posix()
            uri = f"file:{quote(normalized, safe='/:')}?mode=ro"
            return sqlite3.connect(
                uri,
                uri=True,
                isolation_level="DEFERRED",
            )

        return sqlite3.connect(
            path,
            isolation_level="DEFERRED",
        )

    def _configure(
        self,
        connection: sqlite3.Connection,
        *,
        read_only: bool,
    ) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            f"PRAGMA busy_timeout = {self.busy_timeout_ms}"
        )
        if not read_only:
            journal_row = connection.execute(
                f"PRAGMA journal_mode = {JOURNAL_MODE}"
            ).fetchone()
            if journal_row is None or str(journal_row[0]).upper() != JOURNAL_MODE:
                raise sqlite3.OperationalError(
                    f"Unable to enable SQLite journal mode {JOURNAL_MODE}."
                )
            connection.execute(
                f"PRAGMA synchronous = {SYNCHRONOUS_MODE}"
            )
