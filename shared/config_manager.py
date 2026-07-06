"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : config_manager.py
Module      : Shared
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
Configuration Manager

Sprint 5.8:
Attendance Configuration Reader.

This module reads OAS-K_Attendance_Configuration.xlsx.

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class AttendanceMDBConfig:
    """
    Attendance MDB configuration item.
    """

    active: bool
    code: str
    description: str
    mdb_path: Path


@dataclass(slots=True)
class AttendanceConfiguration:
    """
    Attendance configuration result.
    """

    configuration_file: Path
    general: dict[str, Any]
    output: dict[str, Any]
    ho_mdb_list: list[AttendanceMDBConfig]
    branch_mdb_list: list[AttendanceMDBConfig]


class AttendanceConfigurationReader:
    """
    Reader for OAS-K Attendance Configuration workbook.
    """

    REQUIRED_SHEETS: tuple[str, ...] = (
        "General",
        "MDB_HO",
        "MDB_Branch",
        "Output",
    )

    def __init__(
        self,
        configuration_file: str | Path,
    ) -> None:
        self.configuration_file = Path(configuration_file)

    def read(self) -> AttendanceConfiguration:
        """
        Read Attendance Configuration workbook.
        """
        if not self.configuration_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: "
                f"{self.configuration_file}"
            )

        if self.configuration_file.suffix.lower() != ".xlsx":
            raise ValueError(
                "Attendance Configuration must be an .xlsx file."
            )

        logger.info(
            "Reading Attendance Configuration: %s",
            self.configuration_file,
        )

        workbook = load_workbook(
            filename=self.configuration_file,
            data_only=True,
            read_only=True,
        )

        self._validate_required_sheets(workbook.sheetnames)

        general = self._read_key_value_sheet(
            workbook["General"]
        )

        output = self._read_key_value_sheet(
            workbook["Output"]
        )

        ho_mdb_list = self._read_ho_mdb_sheet(
            workbook["MDB_HO"]
        )

        branch_mdb_list = self._read_branch_mdb_sheet(
            workbook["MDB_Branch"]
        )

        workbook.close()

        logger.info(
            "Attendance Configuration loaded. "
            "HO MDB: %s, Branch MDB: %s",
            len(ho_mdb_list),
            len(branch_mdb_list),
        )

        return AttendanceConfiguration(
            configuration_file=self.configuration_file,
            general=general,
            output=output,
            ho_mdb_list=ho_mdb_list,
            branch_mdb_list=branch_mdb_list,
        )

    def _validate_required_sheets(
        self,
        sheet_names: list[str],
    ) -> None:
        """
        Validate required sheets.
        """
        missing_sheets = [
            sheet_name
            for sheet_name in self.REQUIRED_SHEETS
            if sheet_name not in sheet_names
        ]

        if missing_sheets:
            raise ValueError(
                "Missing required sheet(s): "
                + ", ".join(missing_sheets)
            )

    def _read_key_value_sheet(
        self,
        sheet: Any,
    ) -> dict[str, Any]:
        """
        Read sheet with columns:
        Parameter | Value | Description
        """
        result: dict[str, Any] = {}

        rows = list(sheet.iter_rows(values_only=True))

        if not rows:
            return result

        for row in rows[1:]:
            if row is None:
                continue

            parameter = row[0] if len(row) > 0 else None
            value = row[1] if len(row) > 1 else None

            if parameter is None:
                continue

            parameter_text = str(parameter).strip()

            if not parameter_text:
                continue

            result[parameter_text] = value

        return result

    def _read_ho_mdb_sheet(
        self,
        sheet: Any,
    ) -> list[AttendanceMDBConfig]:
        """
        Read MDB_HO sheet.

        Expected columns:
        Active | Company | Description | MDB_Path
        """
        mdb_list: list[AttendanceMDBConfig] = []

        rows = list(sheet.iter_rows(values_only=True))

        if len(rows) <= 1:
            return mdb_list

        for row in rows[1:]:
            active = self._to_bool(row[0] if len(row) > 0 else None)

            if not active:
                continue

            company = self._to_text(row[1] if len(row) > 1 else "")
            description = self._to_text(row[2] if len(row) > 2 else "")
            mdb_path_text = self._to_text(row[3] if len(row) > 3 else "")

            if not mdb_path_text:
                continue

            mdb_list.append(
                AttendanceMDBConfig(
                    active=active,
                    code=company,
                    description=description,
                    mdb_path=Path(mdb_path_text),
                )
            )

        return mdb_list

    def _read_branch_mdb_sheet(
        self,
        sheet: Any,
    ) -> list[AttendanceMDBConfig]:
        """
        Read MDB_Branch sheet.

        Expected columns:
        Active | Branch_Code | Branch_Name | MDB_Path
        """
        mdb_list: list[AttendanceMDBConfig] = []

        rows = list(sheet.iter_rows(values_only=True))

        if len(rows) <= 1:
            return mdb_list

        for row in rows[1:]:
            active = self._to_bool(row[0] if len(row) > 0 else None)

            if not active:
                continue

            branch_code = self._to_text(row[1] if len(row) > 1 else "")
            branch_name = self._to_text(row[2] if len(row) > 2 else "")
            mdb_path_text = self._to_text(row[3] if len(row) > 3 else "")

            if not mdb_path_text:
                continue

            mdb_list.append(
                AttendanceMDBConfig(
                    active=active,
                    code=branch_code,
                    description=branch_name,
                    mdb_path=Path(mdb_path_text),
                )
            )

        return mdb_list

    @staticmethod
    def _to_bool(value: Any) -> bool:
        """
        Convert Excel value to boolean.
        """
        if value is None:
            return False

        value_text = str(value).strip().lower()

        return value_text in (
            "y",
            "yes",
            "true",
            "1",
            "active",
        )

    @staticmethod
    def _to_text(value: Any) -> str:
        """
        Convert Excel value to clean string.
        """
        if value is None:
            return ""

        return str(value).strip()