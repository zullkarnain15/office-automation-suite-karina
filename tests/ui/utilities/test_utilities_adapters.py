from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ui.adapters.attachment_consolidation_adapter import AttachmentConsolidationAdapter
from ui.adapters.comparison_result_adapter import ComparisonResultAdapter
from ui.utilities_models import (
    AttachmentConsolidationCancellationToken,
    AttachmentConsolidationResolvedRequest,
    ComparisonCancellationToken,
    ComparisonResolvedRequest,
)
from utilities.attachment_consolidation.models import (
    ConsolidationArtifacts,
    ConsolidationRequest,
    ConsolidationResult,
    ConsolidationScan,
    ScannedAttachment,
)
from utilities.attendance_reconciliation.models import (
    ReconciliationScan,
    SourceScanResult,
)
import pytest


class ComparisonEngine:
    def __init__(self, scan) -> None:
        self.value = scan
        self.read_only = None

    def scan(self, request, cancel_event, *, read_only=False):
        self.read_only = read_only
        return self.value


def test_comparison_validation_explicitly_uses_read_only_scan(tmp_path: Path) -> None:
    attendance = SourceScanResult("attendance")
    outlook = SourceScanResult("outlook")
    attendance.log_entries.append(type("Log", (), {"status": "USED"})())
    scan = ReconciliationScan(attendance, outlook, ())
    engine = ComparisonEngine(scan)
    adapter = ComparisonResultAdapter(engine)
    resolved = ComparisonResolvedRequest(
        "job",
        tmp_path / "db",
        tmp_path,
        tmp_path,
        "HO",
        "2026-07-01",
        "2026-07-31",
        tmp_path / "does-not-exist",
        False,
        False,
    )
    value = adapter.validate(resolved, ComparisonCancellationToken())
    assert value.valid
    assert engine.read_only is True
    assert not resolved.output_root.exists()


def test_real_comparison_preflight_failure_does_not_create_output(
    tmp_path: Path,
) -> None:
    attendance = tmp_path / "attendance"
    attendance.mkdir()
    outlook = tmp_path / "outlook"
    outlook.mkdir()
    output = tmp_path / "new" / "output"
    resolved = ComparisonResolvedRequest(
        "job",
        tmp_path / "db",
        attendance,
        outlook,
        "HO",
        "2026-07-01",
        "2026-07-31",
        output,
        False,
        False,
    )
    with pytest.raises(ValueError, match="Attendance report"):
        ComparisonResultAdapter().validate(resolved, ComparisonCancellationToken())
    assert not output.exists()


class AttachmentEngine:
    def __init__(self, scan) -> None:
        self.value = scan
        self.max_lines = None

    def scan(self, request, cancel_event):
        return self.value

    def run(self, request, scan, cancel_event, progress, txt_max_lines):
        self.max_lines = txt_max_lines
        folder = request.output_root / "job"
        folder.mkdir(parents=True)
        report = folder / "report.xlsx"
        report.touch()
        log = folder / "Process.log"
        log.touch()
        summary = folder / "summary.json"
        summary.touch()
        artifacts = ConsolidationArtifacts(
            "engine-job", folder, folder, folder, report, log, summary
        )
        now = datetime.now()
        return ConsolidationResult(
            True, request, scan, artifacts, [], [], [], [], txt_max_lines, now, now
        )


def test_attachment_validation_is_non_destructive_and_run_uses_sqlite_override(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    item = source / "one.txt"
    item.touch()
    request = ConsolidationRequest(
        "Merge TXT Attachment", "HO", source, tmp_path / "output"
    )
    scanned = ScannedAttachment(item, "one.txt", ".txt", 0, "READY")
    scan = ConsolidationScan(request.fingerprint(), [scanned])
    engine = AttachmentEngine(scan)
    adapter = AttachmentConsolidationAdapter(engine)
    resolved = AttachmentConsolidationResolvedRequest(
        "audit-job",
        tmp_path / "db",
        source,
        "HO",
        "TXT",
        True,
        tmp_path / "output",
        False,
        4321,
    )
    validation = adapter.validate(resolved, AttachmentConsolidationCancellationToken())
    assert validation.valid and not resolved.output_root.exists()
    result = adapter.run(
        resolved,
        validation.scan,
        cancellation=AttachmentConsolidationCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )
    assert result.success and result.job_id == "audit-job"
    assert engine.max_lines == 4321
