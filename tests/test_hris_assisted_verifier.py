from pathlib import Path
from types import SimpleNamespace

from hris.assisted_verifier import HRISAssistedResultVerifier
from hris.engine import HRISFullUploadEngine
from shared.config_manager import HRISConfiguration


class FakeLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int) -> str:
        return self.text


class FakeFrame:
    def __init__(self, text: str) -> None:
        self.text = text

    def locator(self, selector: str) -> FakeLocator:
        assert selector == "body"
        return FakeLocator(self.text)


def configuration(**upload_values) -> HRISConfiguration:
    upload = {
        "Verification_Wait_Seconds": 0,
        "Verification_Timeout_Seconds": 0,
        "Verification_Poll_Seconds": 0,
        **upload_values,
    }
    return HRISConfiguration(
        Path("config.xlsx"), {}, {}, upload, [], [], []
    )


def test_detects_submitted_and_process_instance() -> None:
    page = SimpleNamespace(
        frames=[FakeFrame("Request submitted. Process Instance 123456 Queued")]
    )
    verifier = HRISAssistedResultVerifier(page, configuration())
    result = verifier.verify_item(
        SimpleNamespace(txt_file_name="one.txt", run_control_id="RC1")
    )
    assert result.status == "SUBMITTED"
    assert result.process_instance == "123456"


def test_failure_text_has_priority() -> None:
    page = SimpleNamespace(
        frames=[FakeFrame("Submitted but Error: Invalid request")]
    )
    verifier = HRISAssistedResultVerifier(
        page,
        configuration(Manual_Verification_On_Error=False),
    )
    result = verifier.verify_item(
        SimpleNamespace(txt_file_name="one.txt", run_control_id="RC1")
    )
    assert result.status == "FAILED"
    assert result.matched_text == "Error"


def test_failure_opens_operator_decision_when_enabled() -> None:
    page = SimpleNamespace(frames=[FakeFrame("Error: request failed")])
    prompts = []
    verifier = HRISAssistedResultVerifier(
        page,
        configuration(),
        manual_callback=lambda prompt: prompts.append(prompt) or "failed",
    )
    result = verifier.verify_item(
        SimpleNamespace(txt_file_name="one.txt", run_control_id="RC1")
    )
    assert result.status == "FAILED"
    assert prompts


def test_unknown_uses_operator_decision() -> None:
    page = SimpleNamespace(frames=[FakeFrame("No recognizable result")])
    verifier = HRISAssistedResultVerifier(
        page,
        configuration(),
        manual_callback=lambda prompt: "submitted",
    )
    result = verifier.verify_item(
        SimpleNamespace(txt_file_name="one.txt", run_control_id="RC1")
    )
    assert result.status == "SUBMITTED"


def test_verified_process_instance_is_persisted_to_plan_item() -> None:
    item = SimpleNamespace(verification_status="", process_instance="")
    verification = SimpleNamespace(
        status="SUBMITTED",
        process_instance="1808729",
    )

    HRISFullUploadEngine._record_assisted_verification(item, verification)

    assert item.verification_status == "SUBMITTED"
    assert item.process_instance == "1808729"
