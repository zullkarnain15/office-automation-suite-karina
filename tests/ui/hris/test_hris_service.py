from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.database import SQLiteConnectionFactory, SchemaManager
from shared.database.repositories import GlobalSettingsRepository, JobRepository
from ui.hris_models import (
    HRISCancellationToken,
    HRISFileResult,
    HRISJobState,
    HRISProgressEvent,
    HRISRunRequest,
    HRISRunResult,
    HRISValidationResult,
)
from ui.services.hris_service import HRISService
from ui.services.protocols import StorageStatusView


class Storage:
    def __init__(self, root: Path, database: Path, valid: bool = True) -> None:
        self.root = root
        self.database = database
        self.valid = valid

    def resolve_status(self):
        return StorageStatusView(
            "READY" if self.valid else "INITIAL_SETUP_REQUIRED",
            self.root,
            self.database,
            self.database.exists(),
            self.valid,
            1 if self.valid else None,
            "test",
            "Tersedia",
            self.root / "recorder_profiles" / "hris",
            self.root / "backup",
            self.root / "output",
            self.root / "logs",
            self.root / "diagnostics",
        )


class Adapter:
    def __init__(self, result: HRISRunResult | None = None) -> None:
        self.result = result

    def validate(self, resolved):
        files = tuple(sorted(resolved.source_folder.glob("*.txt")))
        return HRISValidationResult(
            True,
            True,
            resolved.workflow,
            resolved.period_start,
            resolved.period_end,
            len(files),
            (),
            None,
        )

    def run(self, resolved, **kwargs):
        kwargs["progress"](
            HRISProgressEvent(HRISJobState.WAITING_FOR_LOGIN, "login")
        )
        kwargs["progress"](
            HRISProgressEvent(HRISJobState.WAITING_FOR_USER_UPLOAD, "upload")
        )
        return self.result


def make_database(root: Path, *, hris_use_global_period: bool = True) -> Path:
    database = root / "database" / "OAS-K.db"
    database.parent.mkdir()
    SchemaManager().initialize_database(database, "ui6")
    profile = root / "recorder_profiles" / "hris" / "ho.json"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        json.dumps(
            {
                "profile_version": "1.1",
                "workflow": "HO",
                "screen": {"width": 1920, "height": 1080},
                "browser": {},
                "steps": {},
            }
        ),
        encoding="utf-8",
    )
    with SQLiteConnectionFactory().connect(database) as connection:
        GlobalSettingsRepository(connection).save_global_settings(
            output_root=str(root / "output"),
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
        connection.execute(
            """
            INSERT INTO hris_settings (
                hris_settings_id, use_global_output, use_global_period, hris_url,
                browser_channel, browser_headless, stop_on_first_failure,
                click_profile_path, manual_recovery_enabled, require_profile_match,
                browser_x, browser_y, browser_width, browser_height, browser_zoom,
                verification_enabled, verification_wait_seconds,
                verification_timeout_seconds, verification_poll_seconds,
                verification_success_texts, verification_failure_texts,
                manual_verification_on_unknown, manual_verification_on_error, updated_at
            ) VALUES (1,1,?,'https://hris.test','msedge',0,1,
                'recorder_profiles/hris/ho.json',1,1,0,0,1200,800,100,1,1,10,1,
                'Submitted','Failed',1,1,'2026-07-21T00:00:00')
            """,
            (int(hris_use_global_period),),
        )
        for workflow, sequence, control in (
            ("HO", 1, "001"),
            ("HO", 2, "02"),
            ("BRANCH", 1, "0007"),
        ):
            connection.execute(
                "INSERT INTO hris_run_controls "
                "(workflow,sequence,run_control_id,description,is_active,created_at,updated_at) "
                "VALUES (?,?,?,?,1,'2026-07-21','2026-07-21')",
                (workflow, sequence, control, control),
            )
        connection.execute(
            "INSERT INTO hris_assisted_steps "
            "(sequence,step_name,action,input_source,method,is_required,wait_after_seconds,description,is_active,created_at,updated_at) "
            "VALUES (1,'upload','click','NONE','coordinate',1,0,'Upload',1,'2026-07-21','2026-07-21')"
        )
    return database


def make_request(root: Path, **changes) -> HRISRunRequest:
    source = root / "source"
    source.mkdir(exist_ok=True)
    (source / "Attendance_HO_001.txt").write_text("test", encoding="utf-8")
    values = dict(
        source_folder=source,
        workflow="HO",
        use_global_period=False,
        period_start="2026-07-02",
        period_end="2026-07-03",
        recorder_profile=Path("recorder_profiles/hris/ho.json"),
        manual_upload_acknowledged=True,
    )
    values.update(changes)
    return HRISRunRequest(**values)


def test_database_unavailable_blocks_run_without_creating_anything(tmp_path: Path):
    service = HRISService(Storage(tmp_path, tmp_path / "missing.db", False), Adapter())
    with pytest.raises(RuntimeError, match="database belum tersedia"):
        service.resolve_request(make_request(tmp_path))
    assert not (tmp_path / "output").exists()


def test_defaults_preserve_leading_zero_and_sqlite_source(tmp_path: Path):
    database = make_database(tmp_path)
    defaults = HRISService(Storage(tmp_path, database), Adapter()).load_defaults()
    assert defaults.ho_run_controls == ("001", "02")
    assert defaults.branch_run_controls == ("0007",)
    assert defaults.hris_url == "https://hris.test"


def test_defaults_load_distinct_local_ho_and_branch_txt_sources(tmp_path: Path):
    database = make_database(tmp_path)
    ho = tmp_path / "configured-ho"
    branch = tmp_path / "configured-branch"
    ho.mkdir()
    branch.mkdir()
    with SQLiteConnectionFactory().connect(database) as connection:
        connection.execute(
            "INSERT INTO application_preferences "
            "(preference_key, preference_value, value_type, updated_at) "
            "VALUES ('hris_txt_source_ho', ?, 'TEXT', '2026-08-21')",
            (str(ho),),
        )
        connection.execute(
            "INSERT INTO application_preferences "
            "(preference_key, preference_value, value_type, updated_at) "
            "VALUES ('hris_txt_source_branch', ?, 'TEXT', '2026-08-21')",
            (str(branch),),
        )

    defaults = HRISService(Storage(tmp_path, database), Adapter()).load_defaults()

    assert defaults.ho_txt_source_folder == ho
    assert defaults.branch_txt_source_folder == branch


@pytest.mark.parametrize("workflow", ["HO", "BRANCH"])
def test_resolves_exactly_one_workflow(tmp_path: Path, workflow: str):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    request = make_request(tmp_path, workflow=workflow)
    assert service.resolve_request(request).workflow == workflow


def test_global_and_manual_period(tmp_path: Path):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    global_value = service.resolve_request(
        make_request(tmp_path, use_global_period=True, period_start=None, period_end=None)
    )
    manual = service.resolve_request(make_request(tmp_path))
    assert (global_value.period_start, global_value.period_end) == (
        "2026-07-01",
        "2026-07-31",
    )
    assert (manual.period_start, manual.period_end) == ("2026-07-02", "2026-07-03")


def test_global_period_request_uses_global_dates_even_when_hris_default_is_off(
    tmp_path: Path,
):
    database = make_database(tmp_path, hris_use_global_period=False)
    service = HRISService(Storage(tmp_path, database), Adapter())

    resolved = service.resolve_request(
        make_request(tmp_path, use_global_period=True, period_start=None, period_end=None)
    )

    assert (resolved.period_start, resolved.period_end) == (
        "2026-07-01",
        "2026-07-31",
    )
    assert resolved.used_global_period is True


@pytest.mark.parametrize(
    "start,end",
    [("07/01/2026", "2026-07-02"), ("2026-07-03", "2026-07-02"), (None, None)],
)
def test_invalid_period_is_blocked(tmp_path: Path, start, end):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    with pytest.raises(ValueError):
        service.resolve_request(make_request(tmp_path, period_start=start, period_end=end))


def test_txt_discovery_ignores_non_txt_and_rejects_empty(tmp_path: Path):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    folder = tmp_path / "files"
    folder.mkdir()
    (folder / "b.txt").touch()
    (folder / "a.txt").touch()
    (folder / "ignore.csv").touch()
    assert [item.name for item in service.discover_txt(folder)] == ["a.txt", "b.txt"]
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="tidak memiliki"):
        service.resolve_request(make_request(tmp_path, source_folder=empty))


@pytest.mark.parametrize(
    "profile",
    [Path("C:/absolute.json"), Path("../escape.json"), Path("other/profile.json")],
)
def test_unsafe_profile_reference_is_rejected(tmp_path: Path, profile: Path):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    with pytest.raises(ValueError, match="profile"):
        service.resolve_request(make_request(tmp_path, recorder_profile=profile))


def test_manual_upload_acknowledgement_is_required(tmp_path: Path):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    with pytest.raises(ValueError, match="wajib"):
        service.resolve_request(make_request(tmp_path, manual_upload_acknowledged=False))


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"manual_login": False, "login_id": "", "login_secret": "secret"}, "Username"),
        ({"manual_login": False, "login_id": "karina", "login_secret": ""}, "Password"),
    ],
)
def test_auto_login_requires_session_credentials(tmp_path: Path, changes, message: str):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    with pytest.raises(ValueError, match=message):
        service.resolve_request(make_request(tmp_path, **changes))


def test_auto_login_credentials_are_session_only_on_resolved_request(tmp_path: Path):
    database = make_database(tmp_path)
    service = HRISService(Storage(tmp_path, database), Adapter())
    resolved = service.resolve_request(
        make_request(
            tmp_path,
            manual_login=False,
            login_id="karina",
            login_secret="secret",
        )
    )
    assert resolved.manual_login is False
    assert resolved.login_id == "karina"
    assert resolved.login_secret == "secret"


def test_job_history_records_paused_and_terminal_state(tmp_path: Path):
    database = make_database(tmp_path)
    resolved_service = HRISService(Storage(tmp_path, database), Adapter())
    resolved = resolved_service.resolve_request(make_request(tmp_path))
    result = HRISRunResult(
        True,
        False,
        resolved.job_id,
        "HO",
        "2026-07-21T00:00:00+00:00",
        "2026-07-21T00:00:01+00:00",
        (HRISFileResult(resolved.source_folder / "Attendance_HO_001.txt", "001", "SUCCESS", "ok"),),
    )
    resolved_service.adapter.result = result
    resolved_service.run_job(
        resolved,
        cancellation=HRISCancellationToken(),
        progress=lambda _event: None,
        log=lambda _event: None,
        intervention=lambda _event: None,
    )
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        repository = JobRepository(connection)
        job = repository.get_job_by_id(module_code="HRIS", job_id=resolved.job_id)
        events = connection.execute(
            "SELECT unified_status FROM job_status_events WHERE job_pk=? "
            "ORDER BY status_event_id",
            (job.job_pk,),
        ).fetchall()
    assert job.unified_status == "COMPLETED"
    assert "PAUSED" in [row[0] for row in events]


def test_legacy_fallback_is_session_request_only(tmp_path: Path):
    database = make_database(tmp_path)
    workbook = tmp_path / "legacy.xlsx"
    workbook.touch()
    service = HRISService(Storage(tmp_path, database), Adapter())
    resolved = service.resolve_request(make_request(tmp_path, configuration_path=workbook))
    assert resolved.configuration_path == workbook
    with SQLiteConnectionFactory().connect(database, read_only=True) as connection:
        stored = connection.execute("SELECT click_profile_path FROM hris_settings").fetchone()[0]
    assert stored == "recorder_profiles/hris/ho.json"
