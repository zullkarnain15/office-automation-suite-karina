"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : artifact_writer.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS Job Artifact Writer

Sprint 6.9:
- Create HRIS job folder structure
- Create Upload folder
- Create Failed folder
- Create Report/<JOB_ID> folder
- Create Upload_Process_<JOB_ID>.txt
- Create Upload_Summary_<JOB_ID>.json

No browser automation yet.

=========================================================
"""

from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from hris.job_manager import HRISUploadPlan
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISJobArtifacts:
    """
    HRIS job artifact paths.
    """

    job_id: str
    workflow: str
    hris_output_root: Path
    workflow_root: Path
    upload_folder: Path
    failed_folder: Path
    report_root: Path
    job_report_folder: Path
    process_log_file: Path
    summary_json_file: Path


class HRISJobArtifactWriter:
    """
    HRIS Job Artifact Writer.

    This class is responsible for creating operator-friendly
    HRIS job output folders and initial job files.
    """

    def prepare_job_artifacts(
        self,
        output_root: str | Path,
        workflow: str,
        job_id: str,
        upload_plan: HRISUploadPlan,
    ) -> HRISJobArtifacts:
        """
        Create HRIS folder structure and initial artifacts.
        """
        workflow_label = self._normalize_workflow(workflow)
        output_root_path = Path(output_root)

        if output_root_path.name.lower() == "hris":
            hris_output_root = output_root_path
        else:
            hris_output_root = output_root_path / "HRIS"

        workflow_root = hris_output_root / workflow_label
        upload_folder = workflow_root / "Upload"
        failed_folder = workflow_root / "Failed"
        report_root = workflow_root / "Report"
        job_report_folder = report_root / job_id

        process_log_file = job_report_folder / f"Upload_Process_{job_id}.txt"
        summary_json_file = job_report_folder / f"Upload_Summary_{job_id}.json"

        artifacts = HRISJobArtifacts(
            job_id=job_id,
            workflow=workflow_label,
            hris_output_root=hris_output_root,
            workflow_root=workflow_root,
            upload_folder=upload_folder,
            failed_folder=failed_folder,
            report_root=report_root,
            job_report_folder=job_report_folder,
            process_log_file=process_log_file,
            summary_json_file=summary_json_file,
        )

        self._create_folders(artifacts)
        self.write_process_log(
            artifacts=artifacts,
            message=f"HRIS job artifact prepared. Job ID: {job_id}",
        )
        self.write_initial_summary(
            artifacts=artifacts,
            upload_plan=upload_plan,
            status="READY",
        )

        logger.info(
            "HRIS job artifacts prepared. Job ID=%s, Folder=%s",
            job_id,
            job_report_folder,
        )

        return artifacts

    def write_process_log(
        self,
        artifacts: HRISJobArtifacts,
        message: str,
    ) -> None:
        """
        Append message to upload process text file.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} | {message}\n"

        artifacts.process_log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with artifacts.process_log_file.open(
            mode="a",
            encoding="utf-8",
        ) as file:
            file.write(line)

    def write_initial_summary(
        self,
        artifacts: HRISJobArtifacts,
        upload_plan: HRISUploadPlan,
        status: str,
    ) -> None:
        """
        Write initial upload summary JSON file.
        """
        now = datetime.now().isoformat(timespec="seconds")

        summary = {
            "job_id": artifacts.job_id,
            "module": "HRIS",
            "workflow": artifacts.workflow,
            "status": status,
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "progress_percent": 0,
            "txt_folder": str(upload_plan.txt_folder),
            "total_items": upload_plan.total_txt_files,
            "total_run_controls": upload_plan.total_run_controls,
            "processed_items": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "current_sequence": None,
            "next_sequence": 1 if upload_plan.plan_items else None,
            "current_file": None,
            "message": upload_plan.message,
            "upload_folder": str(artifacts.upload_folder),
            "failed_folder": str(artifacts.failed_folder),
            "report_folder": str(artifacts.job_report_folder),
            "plan_items": [
                self._plan_item_to_dict(item)
                for item in upload_plan.plan_items
            ],
        }

        self.write_summary(
            artifacts=artifacts,
            summary=summary,
        )

    def write_summary(
        self,
        artifacts: HRISJobArtifacts,
        summary: dict[str, Any],
    ) -> None:
        """
        Write upload summary JSON file.
        """
        artifacts.summary_json_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with artifacts.summary_json_file.open(
            mode="w",
            encoding="utf-8",
        ) as file:
            json.dump(
                summary,
                file,
                indent=4,
                ensure_ascii=False,
            )

    def read_summary(
        self,
        summary_json_file: str | Path,
    ) -> dict[str, Any]:
        """
        Read upload summary JSON file.
        """
        summary_path = Path(summary_json_file)

        with summary_path.open(
            mode="r",
            encoding="utf-8",
        ) as file:
            return json.load(file)
        
    def update_summary_after_batch(
        self,
        artifacts: HRISJobArtifacts,
        batch_result: Any,
    ) -> None:
        """
        Update upload summary JSON file after batch upload.
        """
        summary = self.read_summary(
            artifacts.summary_json_file,
        )

        processed_items = (
            batch_result.success_count
            + batch_result.failed_count
        )

        total_items = batch_result.total_items

        if batch_result.failed_count == 0:
            status = "COMPLETED"
            progress_percent = 100
            finished_at = datetime.now().isoformat(timespec="seconds")
            message = "HRIS batch upload completed successfully."
        else:
            status = "FAILED"
            progress_percent = int(
                processed_items / total_items * 100
            ) if total_items else 0
            finished_at = datetime.now().isoformat(timespec="seconds")
            message = "HRIS batch upload finished with failed item(s)."

        summary["status"] = status
        summary["updated_at"] = datetime.now().isoformat(timespec="seconds")
        summary["finished_at"] = finished_at
        summary["progress_percent"] = progress_percent
        summary["processed_items"] = processed_items
        summary["success"] = batch_result.success_count
        summary["failed"] = batch_result.failed_count
        summary["skipped"] = max(
            total_items - processed_items,
            0,
        )
        summary["current_sequence"] = processed_items
        summary["next_sequence"] = None
        summary["current_file"] = None
        summary["message"] = message
        summary["plan_items"] = [
            self._plan_item_to_dict(item)
            for item in batch_result.results
        ]

        self.write_summary(
            artifacts=artifacts,
            summary=summary,
        )

        self.write_process_log(
            artifacts=artifacts,
            message=message,
        )

        self.write_process_log(
            artifacts=artifacts,
            message=(
                "Batch summary updated. "
                f"Processed={processed_items}, "
                f"Success={batch_result.success_count}, "
                f"Failed={batch_result.failed_count}, "
                f"Skipped={summary['skipped']}."
            ),
        )

    def update_summary_after_file_move(
        self,
        artifacts: HRISJobArtifacts,
        move_results: list[Any],
    ) -> None:
        """
        Update upload summary JSON file after TXT files are moved.
        """
        summary = self.read_summary(
            artifacts.summary_json_file,
        )

        move_map = {
            result.txt_file_name: result
            for result in move_results
        }

        for item in summary.get("plan_items", []):
            txt_file_name = item.get("txt_file_name")
            move_result = move_map.get(txt_file_name)

            if move_result is None:
                continue

            if move_result.destination_path is not None:
                item["moved_to"] = str(move_result.destination_path)
            else:
                item["moved_to"] = ""

            item["move_success"] = move_result.success
            item["move_message"] = move_result.message

        self.write_summary(
            artifacts=artifacts,
            summary=summary,
        )

        moved_success = sum(
            1
            for result in move_results
            if result.success
        )

        moved_failed = len(move_results) - moved_success

        self.write_process_log(
            artifacts=artifacts,
            message=(
                "File movement completed. "
                f"Moved={moved_success}, "
                f"Failed={moved_failed}."
            ),
        )


    def _create_folders(
        self,
        artifacts: HRISJobArtifacts,
    ) -> None:
        """
        Create required folders.
        """
        folders = (
            artifacts.hris_output_root,
            artifacts.workflow_root,
            artifacts.upload_folder,
            artifacts.failed_folder,
            artifacts.report_root,
            artifacts.job_report_folder,
        )

        for folder in folders:
            folder.mkdir(
                parents=True,
                exist_ok=True,
            )

    @staticmethod
    def _plan_item_to_dict(item: Any) -> dict[str, Any]:
        """
        Convert upload plan item to JSON-friendly dictionary.
        """
        item_dict = asdict(item)

        if "txt_file_path" in item_dict:
            item_dict["txt_file_path"] = str(item_dict["txt_file_path"])

        return item_dict

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
