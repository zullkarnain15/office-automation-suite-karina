from pathlib import Path
from types import SimpleNamespace

from hris.assisted_replay import HRISAssistedReplayEngine
from shared.config_manager import HRISAssistedStepConfig, HRISConfiguration


class FakeAutomation:
    def __init__(self) -> None:
        self.calls = []

    def click(self, x, y): self.calls.append(("click", x, y))
    def hotkey(self, *keys): self.calls.append(("hotkey", *keys))
    def press(self, key): self.calls.append(("press", key))
    def write(self, value): self.calls.append(("write", value))


def test_coordinate_click_type() -> None:
    step = HRISAssistedStepConfig(
        True, 1, "run_control_id", "click_type", "RUN_CONTROL_ID",
        "coordinate", True, 0, "",
    )
    configuration = HRISConfiguration(
        Path("config.xlsx"), {}, {}, {"Manual_Recovery_Enabled": False},
        [], [], [step],
    )
    automation = FakeAutomation()
    engine = HRISAssistedReplayEngine(
        configuration,
        {"steps": {"run_control_id": {"x": 12, "y": 34}}},
        automation=automation,
    )
    item = SimpleNamespace(
        sequence=1, txt_file_name="one.txt", txt_file_path=Path("one.txt"),
        run_control_id="RC001",
    )
    result = engine.run_item(item, "03/30/2026", "03/30/2026")
    assert result.success
    assert ("click", 12, 34) in automation.calls
    assert ("write", "RC001") in automation.calls
