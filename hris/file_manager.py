"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : file_manager.py
Module      : HRIS
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================
HRIS File Manager

Sprint 6.18:
- Move SUCCESS TXT files to Upload folder
- Move FAILED TXT files to Failed folder
- Avoid filename overwrite

=========================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import move

from hris.artifact_writer import HRISJobArtifacts
from hris.job_manager import FILE_STATUS_FAILED
from hris.job_manager import FILE_STATUS_SUCCESS
from hris.job_manager import HRISUploadPlanItem
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISFileMoveResult:
    """
    HRIS file move result.
    """

    txt_file_name: str
    source_path: Path
    destination_path: Path | None
    status: str
    success: bool
    message: str


class HRISFileManager:
    """
    HRIS File Manager.
    """

    def move_uploaded_files(
        self,
        artifacts: HRISJobArtifacts,
        plan_items: list[HRISUploadPlanItem],
    ) -> list[HRISFileMoveResult]:
        """
        Move uploaded files based on item status.
        """
        results: list[HRISFileMoveResult] = []

        for item in plan_items:
            source_path = Path(item.txt_file_path)

            if item.status == FILE_STATUS_SUCCESS:
                destination_folder = artifacts.upload_folder
            elif item.status == FILE_STATUS_FAILED:
                destination_folder = artifacts.failed_folder
            else:
                results.append(
                    HRISFileMoveResult(
                        txt_file_name=item.txt_file_name,
                        source_path=source_path,
                        destination_path=None,
                        status=item.status,
                        success=False,
                        message="File status is not SUCCESS or FAILED. File not moved.",
                    )
                )
                continue

            result = self._move_one_file(
                source_path=source_path,
                destination_folder=destination_folder,
                status=item.status,
            )

            results.append(result)

        return results

    def _move_one_file(
        self,
        source_path: Path,
        destination_folder: Path,
        status: str,
    ) -> HRISFileMoveResult:
        """
        Move one file safely.
        """
        if not source_path.exists():
            return HRISFileMoveResult(
                txt_file_name=source_path.name,
                source_path=source_path,
                destination_path=None,
                status=status,
                success=False,
                message=f"Source file not found: {source_path}",
            )

        destination_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination_path = self._get_available_destination_path(
            destination_folder=destination_folder,
            file_name=source_path.name,
        )

        move(
            str(source_path),
            str(destination_path),
        )

        logger.info(
            "HRIS TXT file moved. Source=%s, Destination=%s",
            source_path,
            destination_path,
        )

        return HRISFileMoveResult(
            txt_file_name=source_path.name,
            source_path=source_path,
            destination_path=destination_path,
            status=status,
            success=True,
            message="File moved successfully.",
        )

    def _get_available_destination_path(
        self,
        destination_folder: Path,
        file_name: str,
    ) -> Path:
        """
        Return destination path without overwriting existing file.
        """
        destination_path = destination_folder / file_name

        if not destination_path.exists():
            return destination_path

        stem = destination_path.stem
        suffix = destination_path.suffix

        counter = 1

        while True:
            candidate = destination_folder / f"{stem}_{counter:03d}{suffix}"

            if not candidate.exists():
                return candidate

            counter += 1