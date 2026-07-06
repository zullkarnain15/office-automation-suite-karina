"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : job_manager.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Upload Job Manager

Sprint 6.8:
- Scan TXT folder
- Sort TXT files
- Read Run Control list from HRIS configuration
- Pre-validate TXT count vs Run Control count
- Create upload plan
- No browser automation yet

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config_manager import HRISConfiguration
from shared.config_manager import HRISRunControlConfig
from shared.logger import get_logger

logger = get_logger(__name__)


JOB_STATUS_READY = "READY"
JOB_STATUS_VALIDATING = "VALIDATING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_INTERRUPTED = "INTERRUPTED"
JOB_STATUS_FAILED = "FAILED"
JOB_STATUS_CANCELLED = "CANCELLED"

FILE_STATUS_PENDING = "PENDING"
FILE_STATUS_PROCESSING = "PROCESSING"
FILE_STATUS_SUCCESS = "SUCCESS"
FILE_STATUS_FAILED = "FAILED"
FILE_STATUS_SKIPPED = "SKIPPED"


@dataclass(slots=True)
class HRISTXTFileItem:
    """
    HRIS TXT file item.
    """

    sequence: int
    file_name: str
    file_path: Path


@dataclass(slots=True)
class HRISUploadPlanItem:
    """
    HRIS upload plan item.

    One TXT file must use one Run Control ID.
    """

    sequence: int
    txt_file_name: str
    txt_file_path: Path
    workflow: str
    run_control_id: str
    run_control_description: str
    status: str = FILE_STATUS_PENDING
    message: str = ""


@dataclass(slots=True)
class HRISUploadPlan:
    """
    HRIS upload plan result.
    """

    workflow: str
    txt_folder: Path
    total_txt_files: int
    total_run_controls: int
    is_valid: bool
    message: str
    plan_items: list[HRISUploadPlanItem]


class HRISUploadJobManager:
    """
    HRIS Upload Job Manager.

    This class prepares the upload job before browser automation starts.
    """

    def create_upload_plan(
        self,
        configuration: HRISConfiguration,
        txt_folder: str | Path,
        workflow: str,
    ) -> HRISUploadPlan:
        """
        Create upload plan from TXT folder and Run Control list.

        Browser must not be opened before this method passes validation.
        """
        workflow_label = self._normalize_workflow(workflow)
        txt_folder_path = Path(txt_folder)

        logger.info(
            "Creating HRIS upload plan. Workflow=%s, TXT folder=%s",
            workflow_label,
            txt_folder_path,
        )

        txt_files = self.scan_txt_folder(txt_folder_path)
        run_controls = self.get_run_controls(
            configuration=configuration,
            workflow=workflow_label,
        )

        validation_result = self.validate_upload_requirements(
            txt_files=txt_files,
            run_controls=run_controls,
        )

        if not validation_result["is_valid"]:
            return HRISUploadPlan(
                workflow=workflow_label,
                txt_folder=txt_folder_path,
                total_txt_files=len(txt_files),
                total_run_controls=len(run_controls),
                is_valid=False,
                message=validation_result["message"],
                plan_items=[],
            )

        plan_items = self._pair_txt_with_run_controls(
            workflow=workflow_label,
            txt_files=txt_files,
            run_controls=run_controls,
        )

        return HRISUploadPlan(
            workflow=workflow_label,
            txt_folder=txt_folder_path,
            total_txt_files=len(txt_files),
            total_run_controls=len(run_controls),
            is_valid=True,
            message="Upload plan created successfully.",
            plan_items=plan_items,
        )

    def scan_txt_folder(
        self,
        txt_folder: str | Path,
    ) -> list[HRISTXTFileItem]:
        """
        Scan TXT files from selected folder.
        """
        txt_folder_path = Path(txt_folder)

        if not txt_folder_path.exists():
            raise FileNotFoundError(
                f"TXT folder not found: {txt_folder_path}"
            )

        if not txt_folder_path.is_dir():
            raise NotADirectoryError(
                f"TXT folder is not a directory: {txt_folder_path}"
            )

        txt_paths = sorted(
            [
                path
                for path in txt_folder_path.glob("*.txt")
                if path.is_file()
            ],
            key=lambda path: path.name.lower(),
        )

        txt_files: list[HRISTXTFileItem] = []

        for sequence, file_path in enumerate(txt_paths, start=1):
            txt_files.append(
                HRISTXTFileItem(
                    sequence=sequence,
                    file_name=file_path.name,
                    file_path=file_path,
                )
            )

        logger.info(
            "TXT scan finished. Found %s TXT file(s).",
            len(txt_files),
        )

        return txt_files

    def get_run_controls(
        self,
        configuration: HRISConfiguration,
        workflow: str,
    ) -> list[HRISRunControlConfig]:
        """
        Get active Run Control list by workflow.
        """
        workflow_label = self._normalize_workflow(workflow)

        if workflow_label == "HO":
            run_controls = configuration.ho_run_controls
        elif workflow_label == "Branch":
            run_controls = configuration.branch_run_controls
        else:
            raise ValueError(
                "workflow must be 'HO' or 'Branch'."
            )

        sorted_run_controls = sorted(
            run_controls,
            key=lambda item: item.sequence,
        )

        logger.info(
            "Run Control loaded. Workflow=%s, Count=%s",
            workflow_label,
            len(sorted_run_controls),
        )

        return sorted_run_controls

    def validate_upload_requirements(
        self,
        txt_files: list[HRISTXTFileItem],
        run_controls: list[HRISRunControlConfig],
    ) -> dict[str, Any]:
        """
        Validate upload requirements before browser starts.
        """
        if not txt_files:
            return {
                "is_valid": False,
                "message": "No TXT file found in selected TXT folder.",
            }

        if not run_controls:
            return {
                "is_valid": False,
                "message": "No active Run Control ID found for selected workflow.",
            }

        if len(txt_files) > len(run_controls):
            return {
                "is_valid": False,
                "message": (
                    "Run Control ID is not enough. "
                    f"TXT files: {len(txt_files)}, "
                    f"Run Control IDs: {len(run_controls)}."
                ),
            }

        return {
            "is_valid": True,
            "message": "Pre-validation passed.",
        }

    def create_job_id(
        self,
        workflow: str,
    ) -> str:
        """
        Create HRIS Job ID.
        """
        workflow_label = self._normalize_workflow(workflow)

        if workflow_label == "Branch":
            workflow_part = "BRANCH"
        else:
            workflow_part = "HO"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return f"HRIS_{workflow_part}_{timestamp}"

    def _pair_txt_with_run_controls(
        self,
        workflow: str,
        txt_files: list[HRISTXTFileItem],
        run_controls: list[HRISRunControlConfig],
    ) -> list[HRISUploadPlanItem]:
        """
        Pair TXT files with Run Control IDs by sequence.
        """
        plan_items: list[HRISUploadPlanItem] = []

        for txt_file, run_control in zip(txt_files, run_controls):
            plan_items.append(
                HRISUploadPlanItem(
                    sequence=txt_file.sequence,
                    txt_file_name=txt_file.file_name,
                    txt_file_path=txt_file.file_path,
                    workflow=workflow,
                    run_control_id=run_control.run_control_id,
                    run_control_description=run_control.description,
                )
            )

        return plan_items

    @staticmethod
    def _normalize_workflow(workflow: str) -> str:
        """
        Normalize workflow label.
        """
        normalized = workflow.strip().lower()

        if normalized == "ho":
            return "HO"

        if normalized == "branch":
            return "Branch"

        raise ValueError(
            "workflow must be 'HO' or 'Branch'."
        )