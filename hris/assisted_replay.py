"""Configuration-driven assisted upload replay after stable navigation."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from hris.click_profile import HRISClickProfileManager
from shared.config_manager import (
    HRIS_POST_UPLOAD_ASSISTED_STEP_NAMES,
    HRISConfiguration,
    HRISAssistedStepConfig,
)
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HRISAssistedReplayResult:
    success: bool
    message: str
    current_step: str = ""
    action: str = ""
    input_source: str = ""
    error_traceback: str = ""


class HRISAssistedReplayEngine:
    def __init__(
        self,
        configuration: HRISConfiguration,
        profile: dict[str, Any],
        page: Any | None = None,
        manual_recovery_callback: Callable[[str], None] | None = None,
        automation: Any | None = None,
    ) -> None:
        self.configuration = configuration
        self.profile_manager = HRISClickProfileManager(profile)
        self.page = page
        self.manual_recovery_callback = manual_recovery_callback
        self.manual_recovery_enabled = self._to_bool(
            configuration.upload.get("Manual_Recovery_Enabled", True)
        )
        self.automation = automation or self._load_pyautogui()
        self.last_context: dict[str, Any] = {}

    def run_item(
        self,
        plan_item: Any,
        start_date: str,
        end_date: str,
    ) -> HRISAssistedReplayResult:
        steps_by_name = {
            step.step_name: step for step in self.configuration.assisted_steps
        }
        post_upload_steps = [
            steps_by_name[name]
            for name in HRIS_POST_UPLOAD_ASSISTED_STEP_NAMES
            if name in steps_by_name
        ]
        steps = post_upload_steps or self.configuration.assisted_steps
        for step in steps:
            self.last_context = {
                "current_step": step.step_name,
                "action": step.action,
                "input_source": step.input_source,
                "plan_item": {
                    "sequence": getattr(plan_item, "sequence", None),
                    "txt_file_name": getattr(plan_item, "txt_file_name", ""),
                    "run_control_id": getattr(plan_item, "run_control_id", ""),
                },
            }
            try:
                if self.page is not None:
                    self.page.bring_to_front()
                self._run_step(step, plan_item, start_date, end_date)
                time.sleep(max(0.0, step.wait_after_seconds))
            except Exception as error:
                logger.exception("Assisted step failed: %s", step.step_name)
                if not step.required:
                    logger.warning(
                        "Optional assisted step skipped after failure: %s",
                        step.step_name,
                    )
                    continue
                if self.manual_recovery_enabled:
                    try:
                        self._manual_continue(
                            f"Step '{step.step_name}' failed: {error}"
                        )
                        continue
                    except Exception:
                        pass
                return HRISAssistedReplayResult(
                    False,
                    f"Assisted step '{step.step_name}' failed: {error}",
                    step.step_name,
                    step.action,
                    step.input_source,
                    traceback.format_exc(),
                )
        return HRISAssistedReplayResult(True, "Assisted upload item completed.")

    def _run_step(
        self,
        step: HRISAssistedStepConfig,
        plan_item: Any,
        start_date: str,
        end_date: str,
    ) -> None:
        value = self._input_value(step.input_source, plan_item, start_date, end_date)
        if step.action == "wait":
            return
        if step.method == "coordinate":
            x, y = self.profile_manager.get_step_coordinate(step.step_name)
            if step.action != "type":
                self.automation.click(x, y)
            if step.action == "click_type":
                self.automation.hotkey("ctrl", "a")
                self.automation.press("backspace")
                self.automation.write(value)
            elif step.action == "type":
                self.automation.write(value)
            elif step.action == "press":
                self.automation.press(value)
            elif step.action != "click":
                raise ValueError(f"Unsupported coordinate action: {step.action}")
        elif step.method == "assisted" and step.action == "attach_file":
            self._attach_file(Path(value))
        elif step.method == "playwright":
            self._run_playwright_step(step, value)
        elif step.method == "manual" or step.action == "manual_continue":
            self._manual_continue(step.description or step.step_name)
        else:
            raise ValueError(f"Unsupported assisted method: {step.method}")

    def _attach_file(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f"TXT file not found: {path}")
        if self.page is not None:
            try:
                file_input = self.page.locator("input[type='file']").first
                if file_input.count() > 0:
                    file_input.set_input_files(str(path.resolve()))
                    return
            except Exception:
                logger.info("Playwright file input unavailable; using native dialog.")
        self.automation.write(str(path.resolve()))
        self.automation.press("enter")

    def _run_playwright_step(
        self, step: HRISAssistedStepConfig, value: str
    ) -> None:
        if self.page is None:
            raise RuntimeError("Playwright page is unavailable.")
        locator = self.page.get_by_text(step.description or step.step_name).first
        if step.action == "click":
            locator.click()
        elif step.action in {"type", "click_type"}:
            locator.fill(value)
        elif step.action == "press":
            locator.press(value)
        else:
            raise ValueError(f"Unsupported Playwright action: {step.action}")

    def _manual_continue(self, message: str) -> None:
        if self.manual_recovery_callback is not None:
            self.manual_recovery_callback(message)
        else:
            input(f"{message}\nPress ENTER to continue...")

    @staticmethod
    def _input_value(
        source: str, plan_item: Any, start_date: str, end_date: str
    ) -> str:
        values = {
            "NONE": "",
            "RUN_CONTROL_ID": str(plan_item.run_control_id),
            "START_DATE": start_date,
            "END_DATE": end_date,
            "TXT_FILE_PATH": str(plan_item.txt_file_path),
        }
        if source not in values:
            raise ValueError(f"Unsupported Input_Source: {source}")
        return values[source]

    @staticmethod
    def _load_pyautogui() -> Any:
        try:
            import pyautogui
        except ImportError as error:
            raise RuntimeError(
                "pyautogui is required for HRIS assisted automation."
            ) from error
        return pyautogui

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return str(value).strip().lower() in {"true", "1", "yes", "y"}
