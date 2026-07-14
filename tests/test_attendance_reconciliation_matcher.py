from datetime import date, time
from pathlib import Path

import pytest

from utilities.attendance_reconciliation.duplicate_detector import (
    detect_machine_duplicates,
)
from utilities.attendance_reconciliation.duplicate_detector import (
    detect_revision_duplicates,
)
from utilities.attendance_reconciliation.matcher import match_records
from utilities.attendance_reconciliation.models import MachineRecord
from utilities.attendance_reconciliation.models import RevisionRecord


def machine(
    nik: str,
    machine_in=time(8),
    machine_out=time(17),
    *,
    anomaly: bool = False,
    source: str = "machine.xlsx",
) -> MachineRecord:
    return MachineRecord(
        "HO", nik, "Synthetic", date(2026, 7, 1), machine_in, machine_out,
        1 if anomaly else 2, "SINGLE_TAP" if anomaly else "PAIRED",
        "INVALID" if anomaly else "VALID_FOR_TXT", "", "synthetic.mdb",
        Path(source), 2, is_anomaly=anomaly, source_reports=[Path(source)],
    )


def revision(
    nik: str,
    revision_in=time(8),
    revision_out=time(17),
    *,
    source: str = "revision.xlsx",
) -> RevisionRecord:
    return RevisionRecord(
        "HO", nik, date(2026, 7, 1), revision_in, revision_out,
        "attachment.xlsx", Path(source), 2,
        source_reports=[Path(source)], source_rows=[2],
        attachments=["attachment.xlsx"],
    )


def status_for(machines, revisions) -> str:
    comparisons, _ = match_records(
        detect_machine_duplicates(machines),
        detect_revision_duplicates(revisions),
    )
    assert len(comparisons) == 1
    return comparisons[0].status


def test_exact_machine_duplicate_is_deduplicated() -> None:
    result = detect_machine_duplicates([
        machine("001", source="one.xlsx"),
        machine("001", source="two.xlsx"),
    ])
    record = next(iter(result.unique.values()))
    assert record.source_count == 2
    assert result.conflicts == {}
    assert result.audits[0].duplicate_type == "MACHINE_EXACT_DUPLICATE"


def test_machine_time_variants_are_source_conflict() -> None:
    result = detect_machine_duplicates([
        machine("001", source="one.xlsx"),
        machine("001", machine_out=time(18), source="two.xlsx"),
    ])
    assert result.unique == {}
    assert len(result.conflicts) == 1


def test_exact_revision_duplicate_and_conflict() -> None:
    exact = detect_revision_duplicates([
        revision("001", source="one.xlsx"),
        revision("001", source="two.xlsx"),
    ])
    assert next(iter(exact.unique.values())).duplicate_count == 2
    conflict = detect_revision_duplicates([
        revision("001", source="one.xlsx"),
        revision("001", revision_out=time(18), source="two.xlsx"),
    ])
    assert len(conflict.conflicts) == 1


@pytest.mark.parametrize(
    ("machines", "revisions", "expected"),
    [
        ([machine("001")], [], "MACHINE_COMPLETE_NO_REVISION"),
        ([machine("001")], [revision("001")], "MACHINE_COMPLETE_REVISION_MATCH"),
        (
            [machine("001")],
            [revision("001", revision_out=time(18))],
            "MACHINE_COMPLETE_REVISION_DIFFERENT",
        ),
        (
            [machine("001", machine_in=None, anomaly=True)],
            [],
            "MACHINE_ANOMALY_NO_REVISION",
        ),
        (
            [machine("001", machine_in=None, anomaly=True)],
            [revision("001")],
            "MACHINE_ANOMALY_REVISION_AVAILABLE",
        ),
        (
            [machine("001", machine_in=None, anomaly=True)],
            [revision("001", revision_out=None)],
            "MACHINE_ANOMALY_REVISION_INCOMPLETE",
        ),
        ([], [revision("001")], "REVISION_ONLY"),
    ],
)
def test_comparison_statuses(machines, revisions, expected) -> None:
    assert status_for(machines, revisions) == expected


def test_machine_and_revision_conflict_statuses() -> None:
    assert status_for(
        [machine("001"), machine("001", machine_out=time(18))], []
    ) == "MACHINE_SOURCE_CONFLICT"
    assert status_for(
        [machine("001")],
        [revision("001"), revision("001", revision_out=time(18))],
    ) == "MULTIPLE_REVISION_CONFLICT"
