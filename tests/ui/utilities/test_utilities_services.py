from __future__ import annotations

from pathlib import Path

import pytest

from shared.database import SQLiteConnectionFactory, SchemaManager
from shared.database.repositories import GlobalSettingsRepository
from ui.services.attachment_consolidation_service import AttachmentConsolidationService
from ui.services.comparison_result_service import ComparisonResultService
from ui.services.dashboard_service import DashboardService
from ui.services.history_service import HistoryFilters, HistoryService
from ui.services.protocols import StorageStatusView
from ui.services.utilities_service import UtilitiesService
from ui.utilities_models import (
    AttachmentConsolidationCancellationToken,
    AttachmentConsolidationOutputFile,
    AttachmentConsolidationRunRequest,
    AttachmentConsolidationRunResult,
    AttachmentConsolidationValidationResult,
    ComparisonCancellationToken,
    ComparisonOutputFile,
    ComparisonRunRequest,
    ComparisonRunResult,
    ComparisonValidationResult,
    UtilitiesFeature,
    UtilitiesJobPhase,
)


class Storage:
    def __init__(self, root: Path, database: Path, valid: bool = True) -> None:
        self.root, self.database, self.valid = root, database, valid

    def resolve_status(self):
        return StorageStatusView(
            "READY" if self.valid else "INITIAL_SETUP_REQUIRED",
            self.root,
            self.database,
            self.database.exists(),
            self.valid,
            1 if self.valid else None,
            "test",
            "Fake Registry",
            self.root / "profiles",
            self.root / "backup",
            self.root / "output",
            self.root / "logs",
            self.root / "diagnostics",
        )


def make_database(tmp_path: Path) -> Path:
    database = tmp_path / "OAS-K.db"
    SchemaManager().initialize_database(database, "ui7-test")
    with SQLiteConnectionFactory().connect(database) as connection:
        GlobalSettingsRepository(connection).save_global_settings(
            output_root=str(tmp_path / "global-output"),
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        connection.execute(
            "INSERT INTO comparison_settings "
            "(comparison_settings_id,use_global_output,use_global_period,updated_at) "
            "VALUES (1,1,1,'2026-07-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO attachment_consolidation_settings "
            "(attachment_settings_id,use_global_output,txt_max_lines,updated_at) "
            "VALUES (1,1,2500,'2026-07-01T00:00:00')"
        )
    return database


class ComparisonAdapter:
    def __init__(self) -> None:
        self.result = None

    def validate(self, resolved, cancellation):
        return ComparisonValidationResult(True, 1, 1, "comparison.xlsx", scan=object())

    def run(self, resolved, scan, **kwargs):
        return self.result


class AttachmentAdapter:
    def __init__(self) -> None:
        self.result = None

    def validate(self, resolved, cancellation):
        return AttachmentConsolidationValidationResult(
            True,
            2,
            2,
            0,
            0,
            0,
            resolved.txt_max_lines,
            resolved.output_root,
            scan=object(),
        )

    def run(self, resolved, scan, **kwargs):
        return self.result


def test_landing_has_exactly_two_active_features_without_database(
    tmp_path: Path,
) -> None:
    service = UtilitiesService(Storage(tmp_path, tmp_path / "missing.db", False))
    summaries = service.landing_summaries()
    assert tuple(item.feature for item in summaries) == (
        UtilitiesFeature.COMPARISON_RESULT,
        UtilitiesFeature.ATTACHMENT_CONSOLIDATION,
    )
    assert not tmp_path.joinpath("missing.db").exists()


def test_defaults_are_read_only_and_resolve_global_values(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    before = database.stat().st_mtime_ns
    defaults = UtilitiesService(Storage(tmp_path, database)).load_defaults()
    assert defaults.output_root == tmp_path / "global-output"
    assert defaults.period_start == "2026-07-01"
    assert defaults.attachment_txt_max_lines == 2500
    assert database.stat().st_mtime_ns == before


def test_comparison_preflight_is_read_only_and_manual_override_is_not_saved(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)
    attendance, outlook = tmp_path / "attendance", tmp_path / "outlook"
    attendance.mkdir()
    outlook.mkdir()
    manual = tmp_path / "manual-output"
    adapter = ComparisonAdapter()
    service = ComparisonResultService(Storage(tmp_path, database), adapter)
    resolved, validation = service.preflight(
        ComparisonRunRequest(
            attendance,
            outlook,
            "BRANCH",
            False,
            "2026-07-02",
            "2026-07-03",
            False,
            manual,
        ),
        cancellation=ComparisonCancellationToken(),
    )
    assert validation.valid and resolved.output_root == manual
    assert not manual.exists()
    assert not list(tmp_path.rglob("Process.log"))
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM job_history").fetchone()[0] == 0
        assert GlobalSettingsRepository(
            connection
        ).get_global_settings().output_root != str(manual)


def test_comparison_job_audit_uses_feature_code_and_records_existing_files(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)
    attendance, outlook = tmp_path / "attendance", tmp_path / "outlook"
    attendance.mkdir()
    outlook.mkdir()
    adapter = ComparisonAdapter()
    service = ComparisonResultService(Storage(tmp_path, database), adapter)
    resolved, validation = service.preflight(
        ComparisonRunRequest(attendance, outlook, "HO", True, None, None, True, None),
        cancellation=ComparisonCancellationToken(),
    )
    artifact = tmp_path / "comparison.xlsx"
    artifact.touch()
    adapter.result = ComparisonRunResult(
        True,
        False,
        resolved.job_id,
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        (ComparisonOutputFile("REPORT", artifact),),
        total_records=3,
    )
    service.run_job(
        resolved,
        validation,
        cancellation=ComparisonCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        row = connection.execute("SELECT * FROM job_history").fetchone()
        assert (row["module_code"], row["feature_code"], row["workflow"]) == (
            "UTILITIES",
            "COMPARISON_RESULT",
            "HO",
        )
        assert row["unified_status"] == "COMPLETED"
        assert connection.execute("SELECT COUNT(*) FROM job_files").fetchone()[0] == 1
        phases = {
            item["phase"]
            for item in connection.execute("SELECT phase FROM job_status_events")
        }
        assert {
            UtilitiesJobPhase.JOB_CREATED,
            UtilitiesJobPhase.VALIDATION_COMPLETED,
            UtilitiesJobPhase.SOURCE_INSPECTION_STARTED,
            UtilitiesJobPhase.SOURCE_INSPECTION_COMPLETED,
            UtilitiesJobPhase.COMPARISON_STARTED,
            UtilitiesJobPhase.REPORT_WRITING_STARTED,
            UtilitiesJobPhase.OUTPUT_CREATED,
            UtilitiesJobPhase.JOB_COMPLETED,
        } <= phases

    service.request_cancellation(resolved, ComparisonCancellationToken())
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        assert (
            connection.execute("SELECT unified_status FROM job_history").fetchone()[0]
            == "COMPLETED"
        )
    dashboard = DashboardService(Storage(tmp_path, database), database_path=database)
    utilities = next(
        item for item in dashboard.get_module_summaries() if item.module == "UTILITIES"
    )
    assert utilities.total == 1 and utilities.succeeded == 1
    history = HistoryService(Storage(tmp_path, database), database_path=database)
    assert (
        history.search(HistoryFilters(module="UTILITIES")).items[0].feature_code
        == "COMPARISON_RESULT"
    )


def test_attachment_resolves_sqlite_max_lines_and_audits_warning(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    adapter = AttachmentAdapter()
    service = AttachmentConsolidationService(Storage(tmp_path, database), adapter)
    resolved, validation = service.preflight(
        AttachmentConsolidationRunRequest(source, "BRANCH", "TXT", True, True, None),
        cancellation=AttachmentConsolidationCancellationToken(),
    )
    assert resolved.txt_max_lines == 2500
    assert not (tmp_path / "global-output").exists()
    report = tmp_path / "report.xlsx"
    report.touch()
    adapter.result = AttachmentConsolidationRunResult(
        True,
        False,
        resolved.job_id,
        "2026-07-01T00:00:00+00:00",
        "2026-07-01T00:00:01+00:00",
        tmp_path,
        (AttachmentConsolidationOutputFile("REPORT", report),),
        files_scanned=2,
        files_accepted=2,
        warning_count=1,
    )
    service.run_job(
        resolved,
        validation,
        cancellation=AttachmentConsolidationCancellationToken(),
        progress=lambda event: None,
        log=lambda event: None,
    )
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        row = connection.execute("SELECT * FROM job_history").fetchone()
        assert row["feature_code"] == "ATTACHMENT_CONSOLIDATION"
        assert row["unified_status"] == "COMPLETED_WITH_WARNING"


@pytest.mark.parametrize("workflow", ["ALL", "Branch", ""])
def test_invalid_workflows_are_rejected(tmp_path: Path, workflow: str) -> None:
    database = make_database(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    service = AttachmentConsolidationService(
        Storage(tmp_path, database), AttachmentAdapter()
    )
    with pytest.raises(ValueError, match="HO atau BRANCH"):
        service.resolve_request(
            AttachmentConsolidationRunRequest(
                source, workflow, "EXCEL", True, True, None
            )
        )


def test_database_unavailable_blocks_resolution_without_creating_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.db"
    source = tmp_path / "source"
    source.mkdir()
    service = AttachmentConsolidationService(
        Storage(tmp_path, database, False), AttachmentAdapter()
    )
    with pytest.raises(RuntimeError, match="Data Location"):
        service.resolve_request(
            AttachmentConsolidationRunRequest(
                source, "HO", "TXT", True, False, tmp_path
            )
        )
    assert not database.exists()


def test_attachment_blocks_source_equal_to_output(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    service = AttachmentConsolidationService(
        Storage(tmp_path, database), AttachmentAdapter()
    )
    with pytest.raises(ValueError, match="tidak boleh sama"):
        service.resolve_request(
            AttachmentConsolidationRunRequest(source, "HO", "TXT", True, False, source)
        )
