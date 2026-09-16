"""Repeatable synthetic Utilities jobs; never reads the active database.

Run from the repository root: python -m tools.benchmark_utilities --help.
Fixtures and job outputs live in a unique temporary directory. Only the JSON
measurement report is retained. Profiling and Python-allocation measurements
use separate jobs so their overhead is excluded from reported wall times.
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import logging
import platform
import pstats
import statistics
import sys
import tracemalloc
from collections import defaultdict
from contextlib import ExitStack
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

import openpyxl
from openpyxl import Workbook

from utilities.att_data_repair.artifacts import AttDataRepairJobRequest
from utilities.att_data_repair.constants import INVALID_RECORDS_COLUMNS, VALID_RECORDS_COLUMNS
from utilities.att_data_repair.engine import AttDataRepairEngine
from utilities.att_data_repair.models import AttDataRepairRequest
from utilities.att_data_repair.report_discovery import AttDataRepairReportDiscovery
from utilities.att_data_repair.report_reader import AttDataRepairReportReader
from utilities.att_data_repair.txt_writer import AttDataRepairTxtWriter
from utilities.attachment_consolidation.engine import AttachmentConsolidationEngine
from utilities.attachment_consolidation.models import ConsolidationRequest, MODE_EXCEL, MODE_TXT
from utilities.attendance_reconciliation.engine import ReconciliationEngine
from utilities.attendance_reconciliation.models import ReconciliationRequest, SOURCE_MODE_SCAN


CASES = ("attachment_excel", "attachment_txt", "comparison", "repair")
FIXED_NOW = datetime(2026, 8, 20, 9, 0)


def reference_data_style(cell, *, number_format=None, fill=None):
    """Stage-one behavior, retained as an independent equivalence reference."""
    if number_format:
        cell.number_format = number_format
    if fill is not None:
        cell.fill = fill


def reference_output_mapping(file_results, records):
    """Stage-one mapping before removal of repeated Path construction."""
    outputs_by_source = {}
    resolved_sources = {}
    for record in records:
        output_file = getattr(record, "output_file", None)
        if output_file is None:
            continue
        raw_source = Path(record.source_file)
        if raw_source not in resolved_sources:
            resolved_sources[raw_source] = raw_source.resolve()
        source = resolved_sources[raw_source]
        outputs_by_source.setdefault(source, set()).add(Path(output_file))
    for item in file_results:
        item.output_files = sorted(outputs_by_source.get(item.scanned.path.resolve(), set()), key=str)


def _workbook(path, sheets):
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook(write_only=True)
    try:
        for name, rows in sheets:
            sheet = workbook.create_sheet(name)
            for row in rows:
                sheet.append(row)
        workbook.save(path)
    finally:
        workbook.close()


def make_fixtures(root: Path, rows: int) -> None:
    """Deterministic, non-personal inputs with distinct leading-zero IDs."""
    def attachment_rows():
        yield ["NIK", "DATE IN", "TIME IN", "DATE OUT", "TIMEOUT"]
        for i in range(rows):
            yield [f"{i + 1:09d}", "08/03/2026", "08:00", "08/03/2026", "17:00"]
    _workbook(root / "excel" / "input.xlsx", [("Attachment", attachment_rows())])
    txt = root / "txt" / "input.txt"
    txt.parent.mkdir(parents=True)
    with txt.open("w", encoding="utf-8", newline="") as handle:
        for i in range(rows):
            handle.write(f'08/03/2026,{i + 1:09d},08/03/2026,08:00,08/03/2026,17:00\r\n')

    def attendance_rows():
        yield ["NIK", "Nama", "Tanggal", "Jam Masuk", "Jam Keluar", "Tap Count"]
        for i in range(rows):
            yield [f"{i + 1:09d}", "Synthetic", "08/03/2026", "08:00", "17:00", 2]
    _workbook(root / "attendance" / "Export_Attendance_HO_benchmark.xlsx", [
        ("Attendance_Detail", attendance_rows()),
        ("Anomaly", [["NIK", "Nama", "Tanggal", "Jam Masuk", "Jam Keluar", "Tap Count", "Pair Status"]]),
    ])

    def outlook_rows():
        yield ["Workflow", "NIK", "Date_In", "Time_In", "Date_Out", "Time_Out"]
        for i in range(rows):
            yield ["HO", f"{i + 1:09d}", "08/03/2026", "08:00", "08/03/2026", "17:00"]
    _workbook(root / "outlook" / "Outlook_Process_Report_HO_benchmark.xlsx", [
        ("Valid_Data", outlook_rows()), ("Data_Anomaly", [["Anomaly_Code"]]),
    ])

    def repair_rows():
        yield VALID_RECORDS_COLUMNS
        for i in range(rows):
            yield [i + 1, "input.xlsx", "input.xlsx", i + 2, "HO" if i % 2 else "Branch",
                   f"{i + 1:09d}", "08/03/2026", "08:00", "08/03/2026", "17:00", "input.txt", "VALID"]
    _workbook(root / "repair" / "report.xlsx", [
        ("Valid_Records", repair_rows()), ("Invalid_Records", [INVALID_RECORDS_COLUMNS]),
    ])


def run_case(case: str, sources: Path, output: Path, rows: int, *, profile=False, memory=False, reference=False):
    """Time disjoint stages; total additionally includes orchestration and audit."""
    stages = defaultdict(float)
    calls = defaultdict(int)
    with ExitStack() as stack:
        if reference:
            from utilities.att_data_repair import report_writer as repair_writer
            stack.enter_context(patch.object(repair_writer, "apply_data_style", reference_data_style))
            stack.enter_context(patch.object(AttachmentConsolidationEngine, "_assign_output_files", staticmethod(reference_output_mapping)))
        def track(owner, method, label):
            original = getattr(owner, method)
            def measured(*args, **kwargs):
                start = perf_counter()
                try:
                    return original(*args, **kwargs)
                finally:
                    stages[label] += perf_counter() - start
                    calls[label] += 1
            stack.enter_context(patch.object(owner, method, measured))

        if case.startswith("attachment_"):
            engine = AttachmentConsolidationEngine()
            mode = MODE_EXCEL if case == "attachment_excel" else MODE_TXT
            source = sources / ("excel" if mode == MODE_EXCEL else "txt")
            request = ConsolidationRequest(mode, "HO", source, output)
            track(engine.scanner, "scan", "scan")
            track(engine.excel_reader if mode == MODE_EXCEL else engine.txt_reader, "read", "read")
            track(engine.writer, "write", "txt_write")
            track(engine, "_assign_output_files", "output_mapping")
            track(engine.report_writer, "write", "excel_write")
            work = lambda: engine.run(request, txt_max_lines=1000)
            count = lambda result: len(result.records)
        elif case == "comparison":
            from utilities.attendance_reconciliation import engine as comparison_module
            engine = ReconciliationEngine()
            request = ReconciliationRequest(SOURCE_MODE_SCAN, "HO", sources / "attendance", sources / "outlook",
                                            date(2026, 8, 1), date(2026, 8, 31), output)
            track(engine.attendance_reader, "read_folder", "scan_and_read")
            track(engine.outlook_reader, "read_folder", "scan_and_read")
            track(comparison_module, "detect_machine_duplicates", "duplicate_analysis")
            track(comparison_module, "detect_revision_duplicates", "duplicate_analysis")
            track(comparison_module, "match_records", "matching")
            track(engine.excel_writer, "write", "excel_write")
            work = lambda: engine.run(request)
            count = lambda result: len(result.comparisons)
        else:
            reader = AttDataRepairReportReader()
            engine = AttDataRepairEngine(reader=reader, clock=lambda: FIXED_NOW,
                                         txt_writer=AttDataRepairTxtWriter(lambda: 4321))
            request = AttDataRepairJobRequest(AttDataRepairRequest(sources / "repair" / "report.xlsx",
                                              date(2026, 8, 1), date(2026, 8, 31)), output)
            track(reader, "read", "source_read")
            track(engine, "_analyze_records", "repair")
            track(engine.txt_writer, "write", "txt_write")
            track(engine.report_writer, "write", "excel_write")
            def work():
                AttDataRepairReportDiscovery(reader).discover(sources / "repair")
                reader.read(request.analysis_request.source_report)
                return engine.run_job(request)
            count = lambda result: len(result.analysis_result.final_records)

        profiler = cProfile.Profile() if profile else None
        if memory:
            tracemalloc.start()
        start = perf_counter()
        try:
            if profiler:
                profiler.enable()
            result = work()
        finally:
            elapsed = perf_counter() - start
            if profiler:
                profiler.disable()
            peak = tracemalloc.get_traced_memory()[1] if memory else None
            if memory:
                tracemalloc.stop()
        if not getattr(result, "success", getattr(result, "status", None) in {"SUCCESS", "PARTIAL_SUCCESS"}):
            reason = getattr(result, "error_message", None) or getattr(result, "status", "unknown")
            raise RuntimeError(f"Benchmark job failed: {case}: {reason}")
        if count(result) != rows:
            raise AssertionError(f"{case}: expected {rows} records, got {count(result)}")
        measurement = {"seconds": elapsed, "stages_seconds": dict(stages), "stage_calls": dict(calls), "records": count(result)}
        measurement["other_including_validation_and_audit_seconds"] = max(0, elapsed - sum(stages.values()))
        if memory:
            measurement["peak_python_allocations_mib"] = peak / 1024 ** 2
        if profiler:
            stats = pstats.Stats(profiler).stats
            measurement["profile_top_cumulative"] = [
                {"function": f"{key[0]}:{key[1]}:{key[2]}", "calls": value[1], "self_seconds": value[2], "cumulative_seconds": value[3]}
                for key, value in sorted(stats.items(), key=lambda item: item[1][3], reverse=True)[:30]
            ]
        return measurement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--case", choices=(*CASES, "all"), default="all")
    parser.add_argument("--work-root", type=Path, help="Existing writable folder, optionally a network share; only a new temporary child is used")
    parser.add_argument("--output", type=Path, required=True, help="New JSON file to retain measurements")
    parser.add_argument("--profile", action="store_true", help="Separate additional job with cProfile")
    parser.add_argument("--memory", action="store_true", help="Separate additional job measuring Python allocations, not total process RAM")
    parser.add_argument("--compare", action="store_true", help="Alternate stage-one reference and optimized jobs in the same session")
    args = parser.parse_args(argv)
    if args.rows < 1 or args.repeat < 1:
        parser.error("rows and repeat must be positive")
    if args.output.exists():
        parser.error("output already exists; choose a new filename")
    if args.work_root and not args.work_root.is_dir():
        parser.error("work-root must be an existing folder")
    logging.disable(logging.CRITICAL)
    report = {"python": sys.version, "platform": platform.platform(), "openpyxl": openpyxl.__version__,
              "openpyxl_lxml": openpyxl.LXML, "rows_per_input": args.rows, "repeat": args.repeat,
              "fixture_schema": "synthetic-valid-v1", "compare_stage_one": args.compare,
              "work_root": str(args.work_root) if args.work_root else "system temporary folder", "cases": {}}
    code_paths = sorted(Path("utilities").rglob("*.py")) + [Path("outlook/parser.py"), Path(__file__)]
    report["source_sha256"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    with TemporaryDirectory(prefix="oask-utilities-benchmark-", dir=args.work_root) as folder:
        root = Path(folder)
        make_fixtures(root / "sources", args.rows)
        for case in CASES if args.case == "all" else (args.case,):
            samples, references = [], []
            for iteration in range(args.repeat):
                variants = (True, False) if args.compare else (False,)
                if iteration % 2:
                    variants = tuple(reversed(variants))
                for reference in variants:
                    sample = run_case(case, root / "sources", root / case / f'{iteration}-{reference}', args.rows, reference=reference)
                    (references if reference else samples).append(sample)
            entry = {"samples": samples, "median_seconds": statistics.median(s["seconds"] for s in samples)}
            if references:
                entry["reference_samples"] = references
                entry["reference_median_seconds"] = statistics.median(s["seconds"] for s in references)
            if args.profile:
                entry["profile_run"] = run_case(case, root / "sources", root / case / "profile", args.rows, profile=True)
            if args.memory:
                entry["memory_run"] = run_case(case, root / "sources", root / case / "memory", args.rows, memory=True)
                if args.compare:
                    entry["reference_memory_run"] = run_case(case, root / "sources", root / case / "reference-memory", args.rows, memory=True, reference=True)
            report["cases"][case] = entry
            print(f'{case}: median {entry["median_seconds"]:.3f}s ({args.rows} records)', flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
