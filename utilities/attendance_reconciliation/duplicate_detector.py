"""Exact duplicate and conflicting source detection."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from utilities.attendance_reconciliation.models import MachineRecord
from utilities.attendance_reconciliation.models import RecordKey
from utilities.attendance_reconciliation.models import RevisionRecord
from utilities.attendance_reconciliation.models import SourceAuditRecord
from utilities.attendance_reconciliation.normalizer import format_time


@dataclass(slots=True)
class MachineDuplicateResult:
    unique: dict[RecordKey, MachineRecord] = field(default_factory=dict)
    conflicts: dict[RecordKey, list[MachineRecord]] = field(default_factory=dict)
    audits: list[SourceAuditRecord] = field(default_factory=list)


@dataclass(slots=True)
class RevisionDuplicateResult:
    unique: dict[RecordKey, RevisionRecord] = field(default_factory=dict)
    conflicts: dict[RecordKey, list[RevisionRecord]] = field(default_factory=dict)
    audits: list[SourceAuditRecord] = field(default_factory=list)


def detect_machine_duplicates(
    records: list[MachineRecord],
) -> MachineDuplicateResult:
    result = MachineDuplicateResult()
    groups: dict[RecordKey, list[MachineRecord]] = defaultdict(list)
    for record in records:
        groups[record.key].append(record)

    for key, group in groups.items():
        variants: dict[tuple[object, ...], list[MachineRecord]] = defaultdict(list)
        for record in group:
            variants[record.values].append(record)
        if len(variants) > 1:
            result.conflicts[key] = group
            continue

        canonical = group[0]
        sources = [record.source_report for record in group]
        canonical.source_reports = list(dict.fromkeys(sources))
        canonical.source_count = len(group)
        result.unique[key] = canonical
        if len(group) > 1:
            result.audits.append(
                SourceAuditRecord(
                    duplicate_type="MACHINE_EXACT_DUPLICATE",
                    key=key,
                    source_count=len(group),
                    sources=[str(item.source_report) for item in group],
                    values=[
                        f"{format_time(canonical.machine_in)}|"
                        f"{format_time(canonical.machine_out)}"
                    ],
                )
            )
    return result


def detect_revision_duplicates(
    records: list[RevisionRecord],
) -> RevisionDuplicateResult:
    result = RevisionDuplicateResult()
    groups: dict[RecordKey, list[RevisionRecord]] = defaultdict(list)
    for record in records:
        groups[record.key].append(record)

    for key, group in groups.items():
        variants: dict[tuple[object, ...], list[RevisionRecord]] = defaultdict(list)
        for record in group:
            variants[record.values].append(record)
        if len(variants) > 1:
            result.conflicts[key] = group
            continue

        canonical = group[0]
        canonical.duplicate_count = len(group)
        canonical.source_reports = list(
            dict.fromkeys(record.source_report for record in group)
        )
        canonical.source_rows = [record.source_row for record in group]
        canonical.attachments = list(
            dict.fromkeys(
                record.attachment_name
                for record in group
                if record.attachment_name
            )
        )
        result.unique[key] = canonical
        if len(group) > 1:
            result.audits.append(
                SourceAuditRecord(
                    duplicate_type="REVISION_EXACT_DUPLICATE",
                    key=key,
                    source_count=len(group),
                    sources=[str(item.source_report) for item in group],
                    values=[
                        f"{format_time(canonical.revision_in)}|"
                        f"{format_time(canonical.revision_out)}"
                    ],
                )
            )
    return result
