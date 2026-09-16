"""HRIS TXT writer for Att Data Repair."""

from __future__ import annotations

import secrets
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from config.app_config import DATE_FORMAT, TIME_FORMAT
from utilities.att_data_repair.artifacts import TxtArtifact, TxtWriteResult
from utilities.att_data_repair.constants import (
    TXT_FILENAME_PREFIX,
    TXT_UNIQUE_CODE_MAX,
    TXT_UNIQUE_CODE_MIN,
    WORKFLOW_BRANCH,
    WORKFLOW_HO,
)
from utilities.att_data_repair.models import (
    FinalRecord,
    TxtWriteError,
    UniqueCodeCollisionError,
)


class AttDataRepairTxtWriter:
    """Write split workflow-specific HRIS TXT files."""

    def __init__(
        self,
        code_provider: Callable[[], int] | None = None,
        retry_limit: int = 100,
    ) -> None:
        self.code_provider = code_provider or self._secure_code
        self.retry_limit = retry_limit

    def write(
        self,
        records: Sequence[FinalRecord],
        txt_folder: str | Path,
        *,
        max_rows_per_file: int = 10_000,
    ) -> TxtWriteResult:
        """Write records to TXT files grouped by workflow."""

        if max_rows_per_file <= 0:
            raise ValueError("max_rows_per_file harus lebih besar dari nol.")
        if not records:
            return TxtWriteResult()

        folder = Path(txt_folder)
        folder.mkdir(parents=True, exist_ok=True)
        grouped = self._group_by_workflow(records)
        unique_code, plan = self._plan_files(
            grouped,
            folder,
            max_rows_per_file,
        )
        artifacts: list[TxtArtifact] = []
        assignments: dict[str, str] = {}

        for workflow, sequence, chunk, target in plan:
            self._write_one(target, chunk)
            record_ids = tuple(record.record_id for record in chunk)
            for record_id in record_ids:
                assignments[record_id] = target.name
            artifacts.append(
                TxtArtifact(
                    workflow=workflow,
                    sequence=sequence,
                    unique_code=unique_code,
                    file_name=target.name,
                    file_path=target,
                    row_count=len(chunk),
                    record_ids=record_ids,
                )
            )
        return TxtWriteResult(
            artifacts=tuple(artifacts),
            record_txt_assignment=assignments,
            unique_code=unique_code,
        )

    def _plan_files(
        self,
        grouped: dict[str, list[FinalRecord]],
        folder: Path,
        max_rows: int,
    ) -> tuple[int, list[tuple[str, int, list[FinalRecord], Path]]]:
        for _attempt in range(self.retry_limit):
            code = self._next_code()
            plan: list[tuple[str, int, list[FinalRecord], Path]] = []
            collides = False
            for workflow in (WORKFLOW_HO, WORKFLOW_BRANCH):
                records = grouped.get(workflow, [])
                for sequence, chunk in enumerate(
                    _chunks(records, max_rows),
                    start=1,
                ):
                    target = folder / self.file_name(workflow, sequence, code)
                    if target.exists():
                        collides = True
                        break
                    plan.append((workflow, sequence, chunk, target))
                if collides:
                    break
            if not collides:
                return code, plan
        raise UniqueCodeCollisionError(
            "Tidak dapat mendapatkan kode unik TXT Att Data Repair bebas collision."
        )

    def _next_code(self) -> int:
        code = int(self.code_provider())
        if code < TXT_UNIQUE_CODE_MIN or code > TXT_UNIQUE_CODE_MAX:
            raise UniqueCodeCollisionError(
                "Kode unik TXT Att Data Repair harus berada pada rentang 1000-9999."
            )
        return code

    @staticmethod
    def file_name(workflow: str, sequence: int, unique_code: int) -> str:
        """Return the final Att Data Repair TXT filename."""

        return f"{TXT_FILENAME_PREFIX}_{workflow}-{sequence:03d}_{unique_code}.txt"

    @staticmethod
    def _group_by_workflow(
        records: Sequence[FinalRecord],
    ) -> dict[str, list[FinalRecord]]:
        grouped: dict[str, list[FinalRecord]] = defaultdict(list)
        for record in records:
            grouped[record.workflow].append(record)
        return grouped

    @staticmethod
    def _write_one(path: Path, records: Sequence[FinalRecord]) -> None:
        temporary = path.with_name(path.name + ".tmp")
        try:
            if path.exists():
                raise TxtWriteError(f"TXT target sudah ada: {path}")
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                for record in records:
                    handle.write(_format_hris_line(record) + "\n")
            if path.exists():
                raise TxtWriteError(f"TXT target sudah ada: {path}")
            temporary.rename(path)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, TxtWriteError):
                raise
            raise TxtWriteError(f"Gagal menulis TXT {path}: {exc}") from exc

    @staticmethod
    def _secure_code() -> int:
        return secrets.SystemRandom().randint(
            TXT_UNIQUE_CODE_MIN,
            TXT_UNIQUE_CODE_MAX,
        )


def _chunks(records: Sequence[FinalRecord], size: int) -> list[list[FinalRecord]]:
    return [list(records[index:index + size]) for index in range(0, len(records), size)]


def _format_hris_line(record: FinalRecord) -> str:
    fields = (
        record.date_in.strftime(DATE_FORMAT),
        record.nik,
        record.date_in.strftime(DATE_FORMAT),
        record.time_in.strftime(TIME_FORMAT),
        record.date_out.strftime(DATE_FORMAT),
        record.time_out.strftime(TIME_FORMAT),
    )
    return ",".join(_quote(field) for field in fields)


def _quote(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'
