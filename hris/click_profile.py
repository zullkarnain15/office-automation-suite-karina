"""Safe storage and validation for HRIS assisted click coordinates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.config_manager import HRISAssistedStepConfig, HRISConfiguration

SENSITIVE_KEYS = (
    "password", "cookie", "session", "token", "authorization",
    "username", "local_storage", "session_storage", "hidden_input",
)


@dataclass(slots=True)
class HRISProfileValidationResult:
    valid: bool
    message: str


class HRISClickProfileManager:
    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}

    @staticmethod
    def load_profile(path: str | Path) -> dict[str, Any]:
        with Path(path).open(encoding="utf-8") as file:
            profile = json.load(file)
        HRISClickProfileManager._validate_safe_payload(profile)
        return profile

    @staticmethod
    def save_profile(path: str | Path, profile: dict[str, Any]) -> Path:
        HRISClickProfileManager._validate_safe_payload(profile)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return target

    @staticmethod
    def validate_profile(
        profile: dict[str, Any],
        current_screen: tuple[int, int],
        browser_config: dict[str, Any],
        current_scale_percent: int | None = None,
        required_steps: list[HRISAssistedStepConfig] | None = None,
    ) -> HRISProfileValidationResult:
        if profile.get("profile_version") != "1.1":
            return HRISProfileValidationResult(
                False, "PROFILE VERSION OUTDATED - RECALIBRATE"
            )
        screen = profile.get("screen", {})
        browser = profile.get("browser", {})
        expected_browser = {
            "x": int(browser_config.get("Browser_X", 0)),
            "y": int(browser_config.get("Browser_Y", 0)),
            "width": int(browser_config.get("Browser_Width", 1200)),
            "height": int(browser_config.get("Browser_Height", 800)),
            "zoom": int(browser_config.get("Browser_Zoom", 100)),
        }
        if (screen.get("width"), screen.get("height")) != current_screen:
            return HRISProfileValidationResult(False, "SCREEN MISMATCH")
        recorded_scale = screen.get("scale_percent")
        if (
            current_scale_percent is not None
            and recorded_scale is not None
            and int(recorded_scale) != int(current_scale_percent)
        ):
            return HRISProfileValidationResult(False, "DISPLAY SCALE MISMATCH")
        if any(browser.get(key) != value for key, value in expected_browser.items()):
            return HRISProfileValidationResult(False, "BROWSER PROFILE MISMATCH")
        if not isinstance(profile.get("steps"), dict):
            return HRISProfileValidationResult(False, "PROFILE STEPS NOT FOUND")
        profile_steps = profile["steps"]
        for step in required_steps or []:
            if not step.required or step.method != "coordinate":
                continue
            saved_step = profile_steps.get(step.step_name)
            if not isinstance(saved_step, dict):
                return HRISProfileValidationResult(
                    False, f"REQUIRED STEP NOT FOUND: {step.step_name}"
                )
            if saved_step.get("action") != step.action:
                return HRISProfileValidationResult(
                    False, f"STEP ACTION MISMATCH: {step.step_name}"
                )
            try:
                x, y = int(saved_step["x"]), int(saved_step["y"])
            except (KeyError, TypeError, ValueError):
                return HRISProfileValidationResult(
                    False, f"INVALID COORDINATE: {step.step_name}"
                )
            if not (0 <= x < current_screen[0] and 0 <= y < current_screen[1]):
                return HRISProfileValidationResult(
                    False, f"COORDINATE OUTSIDE SCREEN: {step.step_name}"
                )
        return HRISProfileValidationResult(True, "READY")

    def get_step_coordinate(self, step_name: str) -> tuple[int, int]:
        step = self.profile.get("steps", {}).get(step_name)
        if not isinstance(step, dict) or "x" not in step or "y" not in step:
            raise KeyError(f"Coordinate not found for assisted step: {step_name}")
        return int(step["x"]), int(step["y"])

    @staticmethod
    def resolve_profile_path(configuration: HRISConfiguration) -> Path:
        raw_path = str(
            configuration.upload.get(
                "Click_Profile_Path",
                r"config\hris\HRIS_Click_Profile.json",
            )
        ).strip()
        path = Path(raw_path)
        if path.is_absolute():
            return path
        project_root = configuration.configuration_file.parent.parent.parent
        return project_root / path

    @staticmethod
    def _validate_safe_payload(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_lower = str(key).lower()
                if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
                    raise ValueError(f"Sensitive field is not allowed in click profile: {key}")
                HRISClickProfileManager._validate_safe_payload(child, key_lower)
        elif isinstance(value, list):
            for child in value:
                HRISClickProfileManager._validate_safe_payload(child, parent_key)


def load_profile(path: str | Path) -> dict[str, Any]:
    return HRISClickProfileManager.load_profile(path)


def save_profile(path: str | Path, profile: dict[str, Any]) -> Path:
    return HRISClickProfileManager.save_profile(path, profile)


def validate_profile(
    profile: dict[str, Any],
    current_screen: tuple[int, int],
    browser_config: dict[str, Any],
    current_scale_percent: int | None = None,
    required_steps: list[HRISAssistedStepConfig] | None = None,
) -> HRISProfileValidationResult:
    return HRISClickProfileManager.validate_profile(
        profile,
        current_screen,
        browser_config,
        current_scale_percent,
        required_steps,
    )


def get_step_coordinate(
    profile: dict[str, Any],
    step_name: str,
) -> tuple[int, int]:
    return HRISClickProfileManager(profile).get_step_coordinate(step_name)


def resolve_profile_path(configuration: HRISConfiguration) -> Path:
    return HRISClickProfileManager.resolve_profile_path(configuration)
