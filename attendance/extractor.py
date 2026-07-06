"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : extractor.py
Module      : Attendance
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
Attendance MDB Extractor

Sprint 5.1:
MDB Connection and Inspector.

Sprint 5.3:
Attendance Raw Log Extractor.

This module is responsible for reading Microsoft Access MDB
structure and raw attendance log data.

No attendance pairing, validation, TXT writer, or report
business logic is allowed here.

=========================================================
"""

from __future__ import annotations

from datetime import datetime
from datetime import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import pyodbc

from shared.logger import get_logger

logger = get_logger(__name__)


class AttendanceMDBExtractor:
    """
    Microsoft Access MDB extractor.

    This class handles MDB connection, database inspection,
    and raw attendance log extraction.
    """

    DEFAULT_DRIVER: str = "Microsoft Access Driver (*.mdb, *.accdb)"

    def __init__(
        self,
        mdb_path: str | Path,
        driver: str | None = None,
    ) -> None:
        self.mdb_path = Path(mdb_path)
        self.driver = driver or self.DEFAULT_DRIVER
        self.connection: pyodbc.Connection | None = None

    def connect(self) -> None:
        """
        Connect to Microsoft Access MDB file.
        """
        if not self.mdb_path.exists():
            raise FileNotFoundError(
                f"MDB file not found: {self.mdb_path}"
            )

        if self.mdb_path.suffix.lower() != ".mdb":
            raise ValueError(
                f"Invalid MDB file extension: {self.mdb_path.suffix}"
            )

        connection_string = (
            f"DRIVER={{{self.driver}}};"
            f"DBQ={self.mdb_path};"
        )

        logger.info("Connecting to MDB: %s", self.mdb_path)

        self.connection = pyodbc.connect(
            connection_string,
            autocommit=True,
        )

        logger.info("MDB connection established.")

    def close(self) -> None:
        """
        Close MDB connection.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            logger.info("MDB connection closed.")

    def list_tables(
        self,
        include_system_tables: bool = False,
    ) -> list[str]:
        """
        Return list of tables from MDB.
        """
        connection = self._require_connection()

        cursor = connection.cursor()

        tables: list[str] = []

        for row in cursor.tables(tableType="TABLE"):
            table_name = str(row.table_name)

            if (
                not include_system_tables
                and table_name.lower().startswith("msys")
            ):
                continue

            tables.append(table_name)

        tables.sort()

        logger.info("Found %s table(s).", len(tables))

        return tables

    def list_columns(
        self,
        table_name: str,
    ) -> list[dict[str, Any]]:
        """
        Return column metadata for selected table.
        """
        connection = self._require_connection()

        cursor = connection.cursor()

        columns: list[dict[str, Any]] = []

        for row in cursor.columns(table=table_name):
            columns.append(
                {
                    "column_name": getattr(
                        row,
                        "column_name",
                        "",
                    ),
                    "type_name": getattr(
                        row,
                        "type_name",
                        "",
                    ),
                    "column_size": getattr(
                        row,
                        "column_size",
                        "",
                    ),
                    "nullable": getattr(
                        row,
                        "nullable",
                        "",
                    ),
                    "ordinal_position": getattr(
                        row,
                        "ordinal_position",
                        "",
                    ),
                }
            )

        columns.sort(
            key=lambda item: item.get("ordinal_position") or 0
        )

        logger.info(
            "Found %s column(s) in table %s.",
            len(columns),
            table_name,
        )

        return columns

    def preview_table(
        self,
        table_name: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return sample records from selected table.
        """
        connection = self._require_connection()

        safe_limit = max(1, min(limit, 100))
        quoted_table = self._quote_identifier(table_name)

        query = f"SELECT TOP {safe_limit} * FROM {quoted_table}"

        cursor = connection.cursor()
        cursor.execute(query)

        column_names = [
            column[0]
            for column in cursor.description
        ]

        records: list[dict[str, Any]] = []

        for row in cursor.fetchall():
            record = {}

            for index, column_name in enumerate(column_names):
                record[column_name] = row[index]

            records.append(record)

        logger.info(
            "Preview table %s returned %s record(s).",
            table_name,
            len(records),
        )

        return records

    def inspect_database(
        self,
        preview_limit: int = 3,
    ) -> dict[str, Any]:
        """
        Inspect all user tables in MDB.
        """
        inspection_result: dict[str, Any] = {
            "mdb_path": str(self.mdb_path),
            "tables": [],
        }

        tables = self.list_tables()

        for table_name in tables:
            table_info = {
                "table_name": table_name,
                "columns": self.list_columns(table_name),
                "sample_records": self.preview_table(
                    table_name,
                    limit=preview_limit,
                ),
            }

            inspection_result["tables"].append(table_info)

        return inspection_result

    # =====================================================
    # RAW ATTENDANCE LOG EXTRACTION
    # =====================================================

    def fetch_raw_logs(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict[str, Any]]:
        """
        Fetch raw attendance logs from MDB by date range.

        Parameters
        ----------
        date_from : datetime
            Start date selected by user.
        date_to : datetime
            End date selected by user.

        Returns
        -------
        list[dict[str, Any]]

        Notes
        -----
        Date range is inclusive:
            date_from 00:00:00
            until date_to 23:59:59

        The SQL uses exclusive upper bound internally:
            CHECKTIME >= start
            CHECKTIME < next_day
        """
        connection = self._require_connection()

        if date_from > date_to:
            raise ValueError(
                "date_from cannot be greater than date_to."
            )

        start_datetime = datetime.combine(
            date_from.date(),
            time.min,
        )

        end_datetime = datetime.combine(
            date_to.date(),
            time.min,
        ) + timedelta(days=1)

        query = """
            SELECT
                c.[USERID],
                u.[Badgenumber],
                u.[Name],
                c.[CHECKTIME],
                c.[CHECKTYPE],
                c.[VERIFYCODE],
                c.[SENSORID]
            FROM
                [CHECKINOUT] AS c
            LEFT JOIN
                [USERINFO] AS u
            ON
                c.[USERID] = u.[USERID]
            WHERE
                c.[CHECKTIME] >= ?
                AND c.[CHECKTIME] < ?
            ORDER BY
                u.[Badgenumber] ASC,
                c.[CHECKTIME] ASC
        """

        logger.info(
            "Fetching raw attendance logs from %s to %s.",
            start_datetime,
            end_datetime,
        )

        cursor = connection.cursor()

        cursor.execute(
            query,
            start_datetime,
            end_datetime,
        )

        raw_logs: list[dict[str, Any]] = []

        for row in cursor.fetchall():
            nik = ""
            name = ""

            if row[1] is not None:
                nik = str(row[1])

            if row[2] is not None:
                name = str(row[2])

            raw_logs.append(
                {
                    "user_id": row[0],
                    "nik": nik,
                    "name": name,
                    "checktime": row[3],
                    "checktype": row[4],
                    "verify_code": row[5],
                    "sensor_id": row[6],
                    "source_mdb": self.mdb_path.name,
                    "source_mdb_path": str(self.mdb_path),
                }
            )

        logger.info(
            "Fetched %s raw attendance log(s).",
            len(raw_logs),
        )

        return raw_logs

    # =====================================================
    # INTERNAL
    # =====================================================

    def _require_connection(self) -> pyodbc.Connection:
        """
        Return active MDB connection or raise error.
        """
        if self.connection is None:
            raise RuntimeError(
                "MDB connection is not established. "
                "Call connect() first."
            )

        return self.connection

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """
        Quote Access table or column identifier.
        """
        safe_identifier = identifier.replace("]", "]]")
        return f"[{safe_identifier}]"

    def __enter__(self) -> AttendanceMDBExtractor:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()