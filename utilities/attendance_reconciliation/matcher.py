"""Authoritative-machine versus supporting-revision matching."""

from __future__ import annotations

from utilities.attendance_reconciliation.duplicate_detector import (
    MachineDuplicateResult,
)
from utilities.attendance_reconciliation.duplicate_detector import (
    RevisionDuplicateResult,
)
from utilities.attendance_reconciliation.models import ComparisonRecord
from utilities.attendance_reconciliation.models import ConflictRecord
from utilities.attendance_reconciliation.models import InvalidSourceRecord
from utilities.attendance_reconciliation.models import STATUS_MACHINE_ANOMALY_NO_REVISION
from utilities.attendance_reconciliation.models import (
    STATUS_MACHINE_ANOMALY_REVISION_AVAILABLE,
)
from utilities.attendance_reconciliation.models import (
    STATUS_MACHINE_ANOMALY_REVISION_INCOMPLETE,
)
from utilities.attendance_reconciliation.models import (
    STATUS_MACHINE_COMPLETE_NO_REVISION,
)
from utilities.attendance_reconciliation.models import (
    STATUS_MACHINE_COMPLETE_REVISION_DIFFERENT,
)
from utilities.attendance_reconciliation.models import (
    STATUS_MACHINE_COMPLETE_REVISION_MATCH,
)
from utilities.attendance_reconciliation.models import STATUS_MACHINE_SOURCE_CONFLICT
from utilities.attendance_reconciliation.models import (
    STATUS_MULTIPLE_REVISION_CONFLICT,
)
from utilities.attendance_reconciliation.models import STATUS_REVISION_ONLY
from utilities.attendance_reconciliation.normalizer import format_time


STATUS_GUIDE: dict[str, tuple[str, str, bool]] = {
    STATUS_MACHINE_COMPLETE_NO_REVISION: (
        "Normal",
        "Data mesin lengkap dan tidak memiliki revisi.",
        False,
    ),
    STATUS_MACHINE_COMPLETE_REVISION_MATCH: (
        "Normal",
        "Data mesin lengkap dan revisi sama persis.",
        False,
    ),
    STATUS_MACHINE_COMPLETE_REVISION_DIFFERENT: (
        "Perlu Perhatian",
        "Revisi berbeda dari data mesin lengkap; data mesin tetap patokan.",
        True,
    ),
    STATUS_MACHINE_ANOMALY_NO_REVISION: (
        "Anomali",
        "Data mesin tidak lengkap dan revisi tidak tersedia.",
        True,
    ),
    STATUS_MACHINE_ANOMALY_REVISION_AVAILABLE: (
        "Anomali/Revisi",
        "Data mesin anomali dan revisi lengkap tersedia tanpa menimpa mesin.",
        True,
    ),
    STATUS_MACHINE_ANOMALY_REVISION_INCOMPLETE: (
        "Anomali/Revisi",
        "Data mesin anomali dan revisi juga belum lengkap.",
        True,
    ),
    STATUS_REVISION_ONLY: (
        "Revision Only",
        "Data mesin tidak ditemukan dalam report dan periode yang dipilih.",
        True,
    ),
    STATUS_MACHINE_SOURCE_CONFLICT: (
        "Konflik",
        "Beberapa sumber Attendance memiliki waktu berbeda untuk key yang sama.",
        True,
    ),
    STATUS_MULTIPLE_REVISION_CONFLICT: (
        "Konflik",
        "Beberapa revisi Outlook berbeda untuk key yang sama.",
        True,
    ),
}


def match_records(
    machines: MachineDuplicateResult,
    revisions: RevisionDuplicateResult,
) -> tuple[list[ComparisonRecord], list[ConflictRecord]]:
    comparisons: list[ComparisonRecord] = []
    conflicts: list[ConflictRecord] = []
    all_keys = sorted(
        set(machines.unique)
        | set(revisions.unique)
        | set(machines.conflicts)
        | set(revisions.conflicts)
    )

    for key in all_keys:
        if key in machines.conflicts:
            comparisons.append(_comparison(key, STATUS_MACHINE_SOURCE_CONFLICT))
            for record in machines.conflicts[key]:
                conflicts.append(
                    ConflictRecord(
                        STATUS_MACHINE_SOURCE_CONFLICT,
                        key,
                        "Attendance",
                        str(record.source_report),
                        record.source_row,
                        f"In={format_time(record.machine_in)}; "
                        f"Out={format_time(record.machine_out)}",
                        STATUS_GUIDE[STATUS_MACHINE_SOURCE_CONFLICT][1],
                    )
                )
            continue
        if key in revisions.conflicts:
            machine = machines.unique.get(key)
            comparisons.append(
                _comparison(
                    key,
                    STATUS_MULTIPLE_REVISION_CONFLICT,
                    machine=machine,
                )
            )
            for record in revisions.conflicts[key]:
                conflicts.append(
                    ConflictRecord(
                        STATUS_MULTIPLE_REVISION_CONFLICT,
                        key,
                        "Outlook-Revisi",
                        str(record.source_report),
                        record.source_row,
                        f"In={format_time(record.revision_in)}; "
                        f"Out={format_time(record.revision_out)}",
                        STATUS_GUIDE[STATUS_MULTIPLE_REVISION_CONFLICT][1],
                    )
                )
            continue

        machine = machines.unique.get(key)
        revision = revisions.unique.get(key)
        if machine is None:
            comparisons.append(
                _comparison(key, STATUS_REVISION_ONLY, revision=revision)
            )
        elif machine.is_anomaly:
            if revision is None:
                status = STATUS_MACHINE_ANOMALY_NO_REVISION
            elif revision.complete:
                status = STATUS_MACHINE_ANOMALY_REVISION_AVAILABLE
            else:
                status = STATUS_MACHINE_ANOMALY_REVISION_INCOMPLETE
            comparisons.append(
                _comparison(key, status, machine=machine, revision=revision)
            )
        elif revision is None:
            comparisons.append(
                _comparison(
                    key, STATUS_MACHINE_COMPLETE_NO_REVISION, machine=machine
                )
            )
        elif (machine.machine_in, machine.machine_out) == revision.values:
            comparisons.append(
                _comparison(
                    key,
                    STATUS_MACHINE_COMPLETE_REVISION_MATCH,
                    machine,
                    revision,
                )
            )
        else:
            comparisons.append(
                _comparison(
                    key,
                    STATUS_MACHINE_COMPLETE_REVISION_DIFFERENT,
                    machine,
                    revision,
                )
            )

    return comparisons, conflicts


def invalid_conflicts(
    invalid_records: list[InvalidSourceRecord],
) -> list[ConflictRecord]:
    return [
        ConflictRecord(
            conflict_type=item.code,
            key=None,
            source_type=item.source_type,
            source_report=str(item.source_report),
            source_row=item.source_row,
            values=f"Workflow={item.workflow}; NIK={item.nik}; Date={item.raw_date}",
            reason=item.reason,
        )
        for item in invalid_records
    ]


def _comparison(
    key,
    status: str,
    machine=None,
    revision=None,
) -> ComparisonRecord:
    category, description, review = STATUS_GUIDE[status]
    return ComparisonRecord(
        key=key,
        status=status,
        status_description=description,
        category=category,
        review_required=review,
        review_note="Review manual diperlukan." if review else "",
        machine=machine,
        revision=revision,
    )
