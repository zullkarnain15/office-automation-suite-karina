"""Reserve collision-safe job artifact folders."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from utilities.attachment_consolidation.models import ConsolidationArtifacts


class ConsolidationJobManager:
    def reserve(
        self,
        output_root: Path,
        workflow: str,
        now: datetime | None = None,
    ) -> ConsolidationArtifacts:
        current = now or datetime.now()
        base = current.strftime("%Y%m%d_%H%M%S")
        month = current.strftime("%Y-%m")
        root = (
            Path(output_root)
            / "Utilities"
            / "Attachment_Consolidation"
            / workflow
            / month
        )

        for sequence in range(1, 1000):
            job_id = base if sequence == 1 else f"{base}_{sequence:02d}"
            job_folder = root / job_id
            try:
                job_folder.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue

            txt_folder = job_folder / "TXT"
            report_folder = job_folder / "Report"
            txt_folder.mkdir()
            report_folder.mkdir()
            return ConsolidationArtifacts(
                job_id=job_id,
                job_folder=job_folder,
                txt_folder=txt_folder,
                report_folder=report_folder,
                report_file=(
                    report_folder
                    / f"Attachment_Consolidation_{job_id}.xlsx"
                ),
                process_log=job_folder / "Process.log",
                summary_json=job_folder / "summary.json",
            )

        raise RuntimeError(
            f"Tidak dapat membuat job folder Attachment Consolidation: {root}"
        )
