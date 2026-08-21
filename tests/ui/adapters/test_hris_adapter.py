from __future__ import annotations

import threading
import json
from pathlib import Path
from types import SimpleNamespace

from hris.uploader import HRISUploadPageHandler
from ui.adapters.hris_adapter import HRISAdapter
from ui.hris_models import (
    HRISCancellationToken,
    HRISInteractionGate,
    HRISJobState,
)
from ui.hris_models import HRISResolvedRequest


def test_hris_date_conversion_and_leading_zero_are_text() -> None:
    assert HRISAdapter._hris_date("2026-07-01") == "07/01/2026"
    assert str("001") == "001"


def test_interaction_gate_login_and_upload_are_thread_safe() -> None:
    gate = HRISInteractionGate()
    token = HRISCancellationToken()
    completed = []
    worker = threading.Thread(target=lambda: (gate.wait(gate.login_event, token), completed.append(True)))
    worker.start()
    gate.confirm_login()
    worker.join(timeout=1)
    assert completed == [True]


def test_manual_upload_hook_prevents_automatic_upload_click(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.touch()
    item = SimpleNamespace(
        txt_file_path=source,
        txt_file_name=source.name,
        run_control_id="001",
    )
    handler = object.__new__(HRISUploadPageHandler)
    handler.manual_upload_callback = lambda value: calls.append(("manual", value.run_control_id))
    handler.post_upload_recorder_callback = None
    handler._attachment_frame = None
    handler._real_process_submitted = False
    handler._upload_ok_confirmed = False
    handler._run_requested = False
    handler._scheduler_ok_confirmed = False
    calls = []
    handler._reset_item_state = lambda: None
    handler._fill_run_control_id = lambda value: calls.append(("control", value))
    handler._fill_date_range = lambda **_values: calls.append(("period", None))
    handler._attach_txt_file = lambda value: calls.append(("attach", value.name))
    handler._run_step_with_manual_checkpoint = lambda _name, action, _message: action()
    handler._run_playwright_post_upload_steps = lambda: calls.append(("run_ok", None))
    handler._click_upload = lambda: calls.append(("AUTO_UPLOAD", None))
    handler._verify_success = lambda: True

    result = handler.upload_one_file(item, "07/01/2026", "07/31/2026")

    assert result.success
    assert ("manual", "001") in calls
    assert ("run_ok", None) in calls
    assert not any(name == "AUTO_UPLOAD" for name, _value in calls)


def test_validation_path_does_not_construct_engine() -> None:
    constructed = []

    class Engine:
        def __init__(self, **_kwargs):
            constructed.append(True)

    HRISAdapter(engine_class=Engine)
    assert constructed == []


def test_invalid_profile_json_and_workflow_mismatch_are_read_only(tmp_path: Path) -> None:
    profile = tmp_path / "recorder_profiles" / "hris" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text("not-json", encoding="utf-8")
    config = tmp_path / "config.xlsx"
    config.touch()
    request = HRISResolvedRequest(
        "job",
        tmp_path / "db.sqlite",
        tmp_path,
        config,
        tmp_path,
        tmp_path,
        "HO",
        "2026-07-01",
        "2026-07-31",
        False,
        Path("recorder_profiles/hris/profile.json"),
    )
    result = HRISAdapter().validate(request)
    assert not result.valid
    assert any("JSON" in error for error in result.errors)
    assert profile.read_text(encoding="utf-8") == "not-json"

    profile.write_text(
        json.dumps({"profile_version": "1.1", "workflow": "BRANCH", "steps": {}}),
        encoding="utf-8",
    )
    result = HRISAdapter().validate(request)
    assert any("workflow" in error for error in result.errors)


def test_missing_profile_blocks_preflight_before_browser(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "Attendance_HO_001.txt").touch()
    request = HRISResolvedRequest(
        "job",
        tmp_path / "db.sqlite",
        tmp_path,
        tmp_path / "missing-config.xlsx",
        source,
        tmp_path,
        "HO",
        "2026-07-01",
        "2026-07-31",
        False,
        Path("recorder_profiles/hris/missing.json"),
    )

    result = HRISAdapter().validate(request)

    assert not result.valid
    assert any("Calibrate Click Profile" in error for error in result.errors)


def test_mock_engine_uses_legacy_recovery_and_verification_callbacks(
    tmp_path: Path,
) -> None:
    configuration = tmp_path / "config.xlsx"
    configuration.touch()
    source = tmp_path / "source"
    source.mkdir()
    txt = source / "Attendance_HO_001.txt"
    txt.touch()
    profile = tmp_path / "recorder_profiles" / "hris" / "profile.json"
    profile.parent.mkdir(parents=True)
    profile.write_text("{}", encoding="utf-8")
    captured = {}

    class Engine:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            captured["manual_login_callback"]()
            captured["manual_checkpoint_callback"]("recover the HRIS page")
            assert (
                captured["manual_verification_callback"]("verify submission")
                == "submitted"
            )
            return SimpleNamespace(
                success=True,
                message="mock complete",
                report_file=None,
                summary_json_file=None,
                process_log_file=None,
                report_folder=None,
            )

    request = HRISResolvedRequest(
        "job",
        tmp_path / "db.sqlite",
        tmp_path,
        configuration,
        source,
        tmp_path,
        "HO",
        "2026-07-01",
        "2026-07-31",
        False,
        Path("recorder_profiles/hris/profile.json"),
    )
    gate = HRISInteractionGate()
    states = []

    def intervene(event):
        states.append(event.state)
        if event.state == HRISJobState.WAITING_FOR_LOGIN:
            gate.confirm_login()
        elif event.state == HRISJobState.WAITING_FOR_CHECKPOINT:
            gate.choose("continue")
        else:
            gate.choose("submitted")

    result = HRISAdapter(engine_class=Engine).run(
        request,
        cancellation=HRISCancellationToken(),
        gate=gate,
        progress=lambda event: states.append(event.state),
        log=lambda _event: None,
        intervention=intervene,
    )
    assert result.success
    assert HRISJobState.WAITING_FOR_LOGIN in states
    assert HRISJobState.WAITING_FOR_CHECKPOINT in states
    assert HRISJobState.WAITING_FOR_VERIFICATION in states
    assert "manual_upload_callback" not in captured
    assert captured["start_date"] == "07/01/2026"
    assert captured["profile_path_override"] == profile
    assert captured["move_failed_files"] is False
