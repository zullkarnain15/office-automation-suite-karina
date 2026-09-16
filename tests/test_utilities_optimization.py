from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from collections import Counter
from datetime import date
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from utilities.attachment_consolidation.engine import AttachmentConsolidationEngine
from utilities.attachment_consolidation.models import ConsolidationRequest, MODE_TXT
from utilities.attachment_consolidation.report_writer import ConsolidationReportWriter
from utilities.attachment_consolidation.scanner import AttachmentScanner
from utilities.attendance_reconciliation.models import ReconciliationCancelled
from utilities.attendance_reconciliation.scanner import discover_reports
from utilities.att_data_repair.report_reader import AttDataRepairReportReader
from utilities.att_data_repair.models import SourceWorkbookError


def test_consolidation_maps_each_source_once_without_changing_row_order(tmp_path, monkeypatch):
    sources = [tmp_path / "a.xlsx", tmp_path / "b.xlsx"]
    outputs = [tmp_path / "2.txt", tmp_path / "1.txt"]
    records = [SimpleNamespace(
        source_file=sources[i % 2], output_file=outputs[i % 3 == 0],
        source_row=i + 2, nik=f"{i:06d}", date_in=date(2026, 8, 3),
        date_out=date(2026, 8, 3), time_in="08:00", time_out="17:00",
    ) for i in range(200)]
    files = [SimpleNamespace(scanned=SimpleNamespace(path=path)) for path in sources]
    counts = Counter()
    resolve = Path.resolve

    def counted(path, *args, **kwargs):
        counts[path] += 1
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", counted)
    AttachmentConsolidationEngine._assign_output_files(files, records)
    assert [item.output_files for item in files] == [sorted(outputs, key=str)] * 2
    assert sum(counts.values()) == 4  # once per record source, once per inventory file
    counts.clear()
    sheet = SimpleNamespace(append=Mock())
    writer = ConsolidationReportWriter()
    monkeypatch.setattr(writer, "_header", lambda *args: None)
    result = SimpleNamespace(
        records=records, request=SimpleNamespace(workflow="HO"),
        scan=SimpleNamespace(files=[SimpleNamespace(path=p, relative_path=p.name) for p in sources]),
    )
    writer._valid(sheet, result)
    rows = [call.args[0] for call in sheet.append.call_args_list]
    assert [row[5] for row in rows] == [record.nik for record in records]
    assert [row[2] for row in rows] == [record.source_file.name for record in records]
    assert [row[10] for row in rows] == [record.output_file.name for record in records]
    assert sum(counts.values()) == 4


def test_comparison_scans_once_prunes_ignored_trees_and_preserves_audit_order(tmp_path, monkeypatch):
    paths = (
        "HO/Export_Attendance_z.xlsx", "HO/Export_Attendance_a.xlsx",
        "HO/Export_Attendance_empty.xlsx", "HO/~$Export_Attendance_a.xlsx",
        "HO/Backup/deep/Export_Attendance_old.xlsx", "HO/other.xlsx",
    )
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"" if "empty" in name else b"data")
    visited = []
    walk = os.walk

    def tracked(*args, **kwargs):
        for item in walk(*args, **kwargs):
            visited.append(Path(item[0]))
            yield item

    monkeypatch.setattr(os, "walk", tracked)
    candidates, logs = discover_reports(tmp_path, "Attendance")
    assert [p.name for p in candidates] == ["Export_Attendance_a.xlsx", "Export_Attendance_z.xlsx"]
    assert [(item.file_path.name, item.status) for item in logs] == [
        ("Export_Attendance_empty.xlsx", "INVALID"),
        ("~$Export_Attendance_a.xlsx", "TEMPORARY_FILE"),
    ]
    assert visited == [tmp_path, tmp_path / "HO"]
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ReconciliationCancelled):
        discover_reports(tmp_path, "Attendance", cancelled)


def test_attachment_scan_preserves_inventory_without_per_file_path_stat(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    for name in ("a.txt", "~$lock.txt", ".hidden.txt", "summary.json", "ignored.csv"):
        (root / name).write_bytes(b"test")
    original = Path.stat

    def checked(path, *args, **kwargs):
        assert path.parent != root, "File metadata should come from its directory entry"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", checked)
    scan = AttachmentScanner().scan(ConsolidationRequest(
        MODE_TXT, "HO", root, tmp_path / "output",
    ))
    assert [(item.path.name, item.status, item.size_bytes) for item in scan.files] == [
        (".hidden.txt", "HIDDEN_SYSTEM_SKIPPED", 4), ("a.txt", "READY", 4),
        ("summary.json", "OUTPUT_SKIPPED", 4), ("~$lock.txt", "TEMPORARY_SKIPPED", 4),
    ]


def test_attachment_scan_keeps_reparse_hidden_and_system_exclusions(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    entries = []
    for name, directory, attributes in (
        ("linked.txt", False, 0x400), ("junction", True, 0x400),
        ("hidden.txt", False, 0x2), ("system.txt", False, 0x4),
        ("hidden-folder", True, 0x2),
    ):
        path = root / name
        if not directory:
            path.write_bytes(b"data")
        metadata = SimpleNamespace(
            st_mode=stat.S_IFDIR if directory else stat.S_IFREG,
            st_file_attributes=attributes, st_size=4,
        )
        entries.append(SimpleNamespace(
            name=name, path=str(path), stat=Mock(return_value=metadata),
            is_file=Mock(return_value=not directory),
        ))

    @contextmanager
    def scan(folder):
        assert folder == root, "Excluded directories must not be traversed"
        yield iter(entries)

    monkeypatch.setattr(os, "scandir", scan)
    result = AttachmentScanner().scan(ConsolidationRequest(MODE_TXT, "HO", root, tmp_path / "out"))
    assert [(item.path.name, item.status) for item in result.files] == [
        ("hidden.txt", "HIDDEN_SYSTEM_SKIPPED"), ("linked.txt", "SYMLINK_SKIPPED"),
        ("system.txt", "HIDDEN_SYSTEM_SKIPPED"),
    ]
    for entry in entries:
        entry.stat.assert_called_once_with(follow_symlinks=False)


def test_attachment_scan_keeps_warning_for_unreadable_subfolder(tmp_path, monkeypatch):
    root = tmp_path / "source"
    blocked = root / "blocked"
    blocked.mkdir(parents=True)
    (root / "valid.txt").write_bytes(b"data")
    scandir = os.scandir

    def scan(folder):
        if Path(folder) == blocked:
            raise PermissionError("access denied")
        return scandir(folder)

    monkeypatch.setattr(os, "scandir", scan)
    result = AttachmentScanner().scan(ConsolidationRequest(MODE_TXT, "HO", root, tmp_path / "out"))
    assert [item.path.name for item in result.files] == ["valid.txt"]
    assert len(result.warnings) == 1
    assert "access denied" in result.warnings[0]


def test_reader_checks_content_even_when_size_and_timestamp_are_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "report.xlsx"
    path.write_bytes(b"first")
    reader = AttDataRepairReportReader()
    parse = Mock(side_effect=lambda p: (p.read_bytes(),))
    monkeypatch.setattr(reader, "_read_uncached", parse)
    assert reader.read(path) == (b"first",)
    assert reader.read(path) == (b"first",)
    assert parse.call_count == 1
    previous = path.stat()
    path.write_bytes(b"other")
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    assert reader.read(path) == (b"other",)
    assert parse.call_count == 2
    reader.clear_cache()
    assert reader.read(path) == (b"other",)
    assert parse.call_count == 3


def test_reader_does_not_return_cached_data_after_source_is_deleted(tmp_path):
    from tests.test_att_data_repair import _write_report, _default_valid

    path = tmp_path / "report.xlsx"
    _write_report(path, valid_rows=[_default_valid()])
    reader = AttDataRepairReportReader()
    assert reader.read(path)
    path.unlink()
    with pytest.raises(SourceWorkbookError):
        reader.read(path)


def test_reader_matches_uncached_records_after_workbook_rewrite_and_rejects_corruption(tmp_path):
    from tests.test_att_data_repair import _write_report, _default_valid, _default_invalid

    path = tmp_path / "report.xlsx"
    _write_report(path, valid_rows=[_default_valid()])
    reader = AttDataRepairReportReader()
    first = reader.read(path)
    assert reader.read(path) == first
    _write_report(path, valid_rows=[_default_valid(NIK="000002345")], invalid_rows=[_default_invalid()])
    updated = reader.read(path)
    assert updated == reader._read_uncached(path)
    assert updated != first
    assert len(updated) == 2
    path.write_bytes(b"broken workbook")
    with pytest.raises(SourceWorkbookError):
        reader.read(path)


def test_discovery_validation_and_engine_share_verified_workbook(tmp_path, monkeypatch):
    from ui.adapters.att_data_repair_adapter import AttDataRepairAdapter
    from ui.services.att_data_repair_service import AttDataRepairService
    from tests.ui.utilities.test_att_data_repair_service import Storage, make_database, _write_source
    from ui.utilities_models import AttDataRepairRunRequest, AttDataRepairCancellationToken

    database = make_database(tmp_path)
    folder = tmp_path / "source"
    folder.mkdir()
    path = folder / "report.xlsx"
    _write_source(path)
    adapter = AttDataRepairAdapter()
    service = AttDataRepairService(Storage(tmp_path, database), adapter)
    original = adapter.reader._read_uncached
    parse = Mock(wraps=original)
    monkeypatch.setattr(adapter.reader, "_read_uncached", parse)
    request = AttDataRepairRunRequest(
        None, True, None, None, True, None, True, True, source_report_folder=folder,
    )
    token = AttDataRepairCancellationToken()
    resolved, validation = service.preflight(request, cancellation=token)
    assert validation.valid
    assert parse.call_count == 1
    result = service.run_job(resolved, validation, cancellation=token, progress=lambda e: None, log=lambda e: None)
    assert result.success
    assert parse.call_count == 1
    assert adapter.reader._cached_source is None
