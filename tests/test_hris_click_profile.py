from pathlib import Path

import pytest

from hris.click_profile import HRISClickProfileManager


def test_profile_round_trip_and_coordinate(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    profile = {
        "profile_version": "1.1",
        "screen": {"width": 1920, "height": 1080},
        "browser": {"x": 0, "y": 0, "width": 1200, "height": 800, "zoom": 100},
        "steps": {"run": {"x": 10, "y": 20, "action": "click"}},
    }
    HRISClickProfileManager.save_profile(path, profile)
    loaded = HRISClickProfileManager.load_profile(path)
    assert HRISClickProfileManager(loaded).get_step_coordinate("run") == (10, 20)
    assert HRISClickProfileManager.validate_profile(
        loaded,
        (1920, 1080),
        {
            "Browser_X": 0, "Browser_Y": 0, "Browser_Width": 1200,
            "Browser_Height": 800, "Browser_Zoom": 100,
        },
    ).valid


def test_profile_rejects_sensitive_keys(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        HRISClickProfileManager.save_profile(
            tmp_path / "bad.json", {"token": "secret"}
        )
