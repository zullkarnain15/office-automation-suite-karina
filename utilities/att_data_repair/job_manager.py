"""Collision-safe Att Data Repair job folder reservation."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from utilities.att_data_repair.artifacts import JobPaths
from utilities.att_data_repair.constants import FEATURE_FOLDER_NAME
from utilities.att_data_repair.models import JobFolderCreationError

JOB_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<sequence>\d+)$")


class AttDataRepairJobManager:
    """Reserve jobs under Utilities/Att_Data_Repair/YYYY-MM."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self.clock = clock or datetime.now

    def reserve(self, output_root: str | Path) -> JobPaths:
        """Create job, TXT, and Report folders without overwriting."""

        root = Path(output_root)
        utilities_root = root / "Utilities"
        feature_root = utilities_root / FEATURE_FOLDER_NAME
        date_label = self.clock().strftime("%Y-%m-%d")
        month_root = feature_root / date_label[:7]

        try:
            month_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise JobFolderCreationError(
                f"Tidak dapat membuat root Att Data Repair: {feature_root}: {exc}"
            ) from exc

        sequence = self._next_sequence(feature_root, date_label)
        while True:
            job_id = f"{date_label}_{sequence:02d}"
            job_folder = month_root / job_id
            try:
                job_folder.mkdir(parents=False, exist_ok=False)
                txt_folder = job_folder / "TXT"
                report_folder = job_folder / "Report"
                txt_folder.mkdir(exist_ok=False)
                report_folder.mkdir(exist_ok=False)
                return JobPaths(
                    output_root=root,
                    utilities_root=utilities_root,
                    feature_root=feature_root,
                    job_folder=job_folder,
                    txt_folder=txt_folder,
                    report_folder=report_folder,
                    process_log=job_folder / "Process.log",
                    summary_json=job_folder / "summary.json",
                    job_id=job_id,
                )
            except FileExistsError:
                sequence += 1
                continue
            except OSError as exc:
                raise JobFolderCreationError(
                    f"Tidak dapat membuat job folder Att Data Repair: "
                    f"{job_folder}: {exc}"
                ) from exc

    @staticmethod
    def _next_sequence(feature_root: Path, date_label: str) -> int:
        sequences = []
        # Include legacy flat jobs so rollout does not restart the sequence for
        # a date that already has output from an older application version.
        for parent in (feature_root, feature_root / date_label[:7]):
            try:
                children = tuple(parent.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir():
                    continue
                match = JOB_PATTERN.fullmatch(child.name)
                if match is None or match.group("date") != date_label:
                    continue
                try:
                    sequences.append(int(match.group("sequence")))
                except ValueError:
                    continue
        return max(sequences, default=0) + 1
