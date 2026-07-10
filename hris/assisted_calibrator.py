"""Interactive creation of the HRIS assisted click profile."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from hris.click_profile import HRISClickProfileManager
from shared.config_manager import (
    HRIS_POST_UPLOAD_ASSISTED_STEP_NAMES,
    HRISConfiguration,
    HRISConfigurationReader,
)


class HRISAssistedCalibrator:
    def __init__(
        self,
        configuration_file: str | Path,
        instruction_callback: Callable[[str], None] | None = None,
        coordinate_callback: Callable[[str], tuple[int, int]] | None = None,
        browser_manager_factory: Callable[[HRISConfiguration], Any] | None = None,
        automation: Any | None = None,
    ) -> None:
        self.configuration_file = Path(configuration_file)
        self.instruction_callback = instruction_callback
        self.coordinate_callback = coordinate_callback
        self.browser_manager_factory = browser_manager_factory
        self.automation = automation or self._load_pyautogui()

    def run(self) -> Path:
        configuration = HRISConfigurationReader(self.configuration_file).read()
        browser_manager = self._create_browser_manager(configuration)
        try:
            browser_manager.open_login_page()
            self._prompt(
                "Microsoft Edge sudah dibuka dari URL HRIS pada konfigurasi.\n\n"
                "Silakan login dan navigasi manual sampai halaman "
                "Overtime Upload Attendance. Pastikan halaman siap, "
                "lalu konfirmasi untuk memulai kalibrasi."
            )

            screen = self.automation.size()
            profile = {
                "profile_name": "HRIS_Default",
                "profile_version": "1.1",
                "capture_mode": "global_hotkey_f8",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "screen": {
                    "width": int(screen.width),
                    "height": int(screen.height),
                    "scale_percent": self._get_scale_percent(),
                },
                "browser": self._browser_profile(configuration),
                "steps": {},
            }
            post_upload_steps = [
                step
                for step in configuration.assisted_steps
                if step.step_name in HRIS_POST_UPLOAD_ASSISTED_STEP_NAMES
            ]
            calibration_steps = post_upload_steps or configuration.assisted_steps
            for step in calibration_steps:
                if step.method != "coordinate":
                    continue
                message = (
                    f"Kalibrasi step: {step.step_name}\n"
                    f"{step.description}\n\n"
                    "Setelah memulai hitung mundur, arahkan mouse ke target "
                    "dan diamkan sampai koordinat diambil."
                )
                x, y = self._capture_coordinate(message)
                profile["steps"][step.step_name] = {
                    "x": x,
                    "y": y,
                    "action": step.action,
                }

            validation = HRISClickProfileManager.validate_profile(
                profile,
                (int(screen.width), int(screen.height)),
                configuration.upload,
                current_scale_percent=self._get_scale_percent(),
                required_steps=calibration_steps,
            )
            if not validation.valid:
                raise RuntimeError(
                    f"Click profile validation failed: {validation.message}"
                )

            path = HRISClickProfileManager.resolve_profile_path(configuration)
            return HRISClickProfileManager.save_profile(path, profile)
        finally:
            browser_manager.close()

    def _prompt(self, message: str) -> None:
        if self.instruction_callback:
            self.instruction_callback(message)
        else:
            input(f"{message}\n")

    def _capture_coordinate(self, message: str) -> tuple[int, int]:
        if self.coordinate_callback is not None:
            return self.coordinate_callback(message)

        print(message)
        input(
            "Arahkan pointer ke target, lalu tekan ENTER untuk menyimpan "
            "koordinat..."
        )
        position = self.automation.position()
        return int(position.x), int(position.y)

    def _create_browser_manager(
        self,
        configuration: HRISConfiguration,
    ) -> Any:
        if self.browser_manager_factory is not None:
            return self.browser_manager_factory(configuration)
        from hris.browser import HRISBrowserManager
        return HRISBrowserManager(configuration)

    @staticmethod
    def _browser_profile(configuration: HRISConfiguration) -> dict[str, int]:
        upload = configuration.upload
        return {
            "x": int(upload.get("Browser_X", 0)),
            "y": int(upload.get("Browser_Y", 0)),
            "width": int(upload.get("Browser_Width", 1200)),
            "height": int(upload.get("Browser_Height", 800)),
            "zoom": int(upload.get("Browser_Zoom", 100)),
        }

    @staticmethod
    def _get_scale_percent() -> int:
        try:
            import ctypes
            return round(ctypes.windll.shcore.GetScaleFactorForDevice(0))
        except Exception:
            return 100

    @staticmethod
    def _load_pyautogui() -> Any:
        try:
            import pyautogui
        except ImportError as error:
            raise RuntimeError("pyautogui is required for calibration.") from error
        return pyautogui
