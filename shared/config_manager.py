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

This module contains configuration readers for OAS-K.

Current readers:
- AttendanceConfigurationReader
- HRISConfigurationReader

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from shared.logger import get_logger

logger = get_logger(__name__)


# =========================================================
# ATTENDANCE CONFIGURATION
# =========================================================


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

    def get_output_folder(self) -> Path | None:
        """
        Return configured Attendance output folder, if available.
        """
        output_value = self._get_first_value(
            self.general,
            (
                "OutputFolder",
                "Output_Folder",
                "Output_Root",
            ),
        )

        if output_value is None:
            output_value = self._get_first_value(
                self.output,
                ("Output_Root",),
            )

        if output_value is None:
            return None

        output_path = Path(str(output_value).strip())

        if not str(output_path):
            return None

        if output_path.is_absolute():
            return output_path

        return self.configuration_file.parent.parent / output_path

    @staticmethod
    def _get_first_value(
        values: dict[str, Any],
        keys: tuple[str, ...],
    ) -> Any:
        """
        Return the first non-empty configuration value for keys.
        """
        for key in keys:
            value = values.get(key)

            if value is None:
                continue

            value_text = str(value).strip()

            if value_text:
                return value

        return None


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


# =========================================================
# HRIS CONFIGURATION
# =========================================================


@dataclass(slots=True)
class HRISRunControlConfig:
    """
    HRIS Run Control configuration item.
    """

    active: bool
    sequence: int
    workflow: str
    run_control_id: str
    description: str


@dataclass(slots=True)
class HRISConfiguration:
    """
    HRIS configuration result.
    """

    configuration_file: Path
    general: dict[str, Any]
    browser: dict[str, Any]
    upload: dict[str, Any]
    ho_run_controls: list[HRISRunControlConfig]
    branch_run_controls: list[HRISRunControlConfig]

    def get_output_folder(self) -> Path | None:
        """
        Return configured HRIS output folder, if available.
        """
        output_value = self._get_first_value(
            self.general,
            (
                "Folder_Upload_Path",
                "OutputFolder",
                "Output_Folder",
                "Output_Root",
            ),
        )

        if output_value is None:
            output_value = self._get_first_value(
                self.upload,
                (
                    "Folder_Upload_Path",
                    "OutputFolder",
                    "Output_Folder",
                    "Output_Root",
                ),
            )

        if output_value is None:
            return None

        output_path = Path(str(output_value).strip())

        if not str(output_path):
            return None

        if output_path.is_absolute():
            return output_path

        return self.configuration_file.parent.parent / output_path

    @staticmethod
    def _get_first_value(
        values: dict[str, Any],
        keys: tuple[str, ...],
    ) -> Any:
        """
        Return the first non-empty configuration value for keys.
        """
        for key in keys:
            value = values.get(key)

            if value is None:
                continue

            value_text = str(value).strip()

            if value_text:
                return value

        return None


class HRISConfigurationReader:
    """
    Reader for OAS-K HRIS Configuration workbook.
    """

    REQUIRED_SHEETS: tuple[str, ...] = (
        "General",
        "Run_Control",
        "Browser",
        "Upload",
        "Reference",
    )

    def __init__(
        self,
        configuration_file: str | Path,
    ) -> None:
        self.configuration_file = Path(configuration_file)

    def read(self) -> HRISConfiguration:
        """
        Read HRIS Configuration workbook.
        """
        if not self.configuration_file.exists():
            raise FileNotFoundError(
                f"HRIS Configuration file not found: "
                f"{self.configuration_file}"
            )

        if self.configuration_file.suffix.lower() != ".xlsx":
            raise ValueError(
                "HRIS Configuration must be an .xlsx file."
            )

        logger.info(
            "Reading HRIS Configuration: %s",
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

        browser = self._read_key_value_sheet(
            workbook["Browser"]
        )

        upload = self._read_key_value_sheet(
            workbook["Upload"]
        )

        run_controls = self._read_run_control_sheet(
            workbook["Run_Control"]
        )

        workbook.close()

        ho_run_controls = [
            item
            for item in run_controls
            if item.workflow == "HO"
        ]

        branch_run_controls = [
            item
            for item in run_controls
            if item.workflow == "Branch"
        ]

        logger.info(
            "HRIS Configuration loaded. "
            "HO Run Control: %s, Branch Run Control: %s",
            len(ho_run_controls),
            len(branch_run_controls),
        )

        return HRISConfiguration(
            configuration_file=self.configuration_file,
            general=general,
            browser=browser,
            upload=upload,
            ho_run_controls=ho_run_controls,
            branch_run_controls=branch_run_controls,
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
                "Missing required HRIS sheet(s): "
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

    def _read_run_control_sheet(
        self,
        sheet: Any,
    ) -> list[HRISRunControlConfig]:
        """
        Read Run_Control sheet.

        Expected columns:
        Active | Sequence | Workflow | Run_Control_ID | Description
        """
        run_controls: list[HRISRunControlConfig] = []

        rows = list(sheet.iter_rows(values_only=True))

        if len(rows) <= 1:
            return run_controls

        for row in rows[1:]:
            if row is None:
                continue

            active = self._to_bool(row[0] if len(row) > 0 else None)

            if not active:
                continue

            sequence = self._to_int(row[1] if len(row) > 1 else None)
            workflow = self._normalize_workflow(
                row[2] if len(row) > 2 else None
            )
            run_control_id = self._to_text(
                row[3] if len(row) > 3 else ""
            )
            description = self._to_text(
                row[4] if len(row) > 4 else ""
            )

            if sequence <= 0:
                continue

            if workflow not in ("HO", "Branch"):
                continue

            if not run_control_id:
                continue

            run_controls.append(
                HRISRunControlConfig(
                    active=active,
                    sequence=sequence,
                    workflow=workflow,
                    run_control_id=run_control_id,
                    description=description,
                )
            )

        run_controls.sort(
            key=lambda item: (
                item.workflow,
                item.sequence,
            )
        )

        return run_controls

    @staticmethod
    def get_run_controls_by_workflow(
        configuration: HRISConfiguration,
        workflow: str,
    ) -> list[HRISRunControlConfig]:
        """
        Return active Run Control list by workflow.
        """
        workflow_label = HRISConfigurationReader._normalize_workflow(
            workflow
        )

        if workflow_label == "HO":
            return configuration.ho_run_controls

        if workflow_label == "Branch":
            return configuration.branch_run_controls

        raise ValueError(
            "workflow must be 'HO' or 'Branch'."
        )

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
    def _to_int(value: Any) -> int:
        """
        Convert Excel value to integer.
        """
        if value is None:
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_text(value: Any) -> str:
        """
        Convert Excel value to clean string.

        Important:
        Run_Control_ID must remain text.
        Example:
        001 must stay 001.
        02 must stay 02.
        """
        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _normalize_workflow(value: Any) -> str:
        """
        Normalize workflow value.
        """
        value_text = str(value or "").strip().lower()

        if value_text == "ho":
            return "HO"

        if value_text == "branch":
            return "Branch"

        return ""
