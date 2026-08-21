from __future__ import annotations

from pathlib import Path

from ui.hris_models import (
    HRISCancellationToken,
    HRISInteractionGate,
    HRISJobState,
    TERMINAL_HRIS_STATES,
)


def test_cancellation_releases_login_and_upload_waits() -> None:
    token = HRISCancellationToken()
    gate = HRISInteractionGate()
    token.request()
    gate.login_event.set()
    try:
        gate.wait(gate.login_event, token)
    except RuntimeError as exc:
        assert "dibatalkan" in str(exc)
    else:
        raise AssertionError("Cancellation must stop the gate.")


def test_terminal_state_contract_prevents_late_cancel_overwrite() -> None:
    assert HRISJobState.COMPLETED in TERMINAL_HRIS_STATES
    assert HRISJobState.FAILED in TERMINAL_HRIS_STATES
    assert HRISJobState.CANCELLED in TERMINAL_HRIS_STATES
    assert HRISJobState.CANCEL_REQUESTED not in TERMINAL_HRIS_STATES


def test_models_never_contain_credentials() -> None:
    source = Path("ui/hris_models.py").read_text(encoding="utf-8").casefold()
    assert "username" not in source
    assert "password" not in source
    assert "credential" not in source
