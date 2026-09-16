"""Resolve the updater executable resource across source and PyInstaller modes."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from config.app_config import PROJECT_ROOT
from shared.update.exceptions import UpdateApplyError
from shared.update.path_safety import resolved

UPDATER_EXECUTABLE_NAME = "OAS-K-Updater.exe"
BUNDLED_UPDATER_RELATIVE_PATH = Path("updater") / UPDATER_EXECUTABLE_NAME


@dataclass(frozen=True, slots=True)
class UpdaterResource:
    path: Path
    kind: str

    @property
    def is_executable(self) -> bool:
        return self.kind == "executable"


def default_updater_resource(project_root: str | Path | None = None) -> UpdaterResource:
    """Return the updater resource bundled with the app or available in source mode."""

    if _is_frozen():
        bundled = _frozen_resource_root() / BUNDLED_UPDATER_RELATIVE_PATH
        if not bundled.is_file():
            raise UpdateApplyError(
                "OAS-K-Updater.exe tidak ditemukan dalam paket aplikasi."
            )
        return UpdaterResource(resolved(bundled), "executable")

    root = resolved(project_root or PROJECT_ROOT)
    built_exe = root / "dist" / "updater" / UPDATER_EXECUTABLE_NAME
    if built_exe.is_file():
        return UpdaterResource(resolved(built_exe), "executable")

    source_main = root / "updater" / "main.py"
    if source_main.is_file():
        return UpdaterResource(resolved(source_main), "python_script")

    raise UpdateApplyError("OAS-K-Updater.exe tidak ditemukan dalam paket aplikasi.")


def explicit_updater_resource(value: str | Path) -> UpdaterResource:
    """Resolve a caller-supplied updater resource path."""

    source = resolved(value)
    if source.is_file():
        if source.name.casefold() == UPDATER_EXECUTABLE_NAME.casefold():
            return UpdaterResource(source, "executable")
        if source.name == "main.py":
            return UpdaterResource(source, "python_script")
        raise UpdateApplyError(f"Updater source tidak didukung: {source}")
    if source.is_dir():
        executable = source / UPDATER_EXECUTABLE_NAME
        if executable.is_file():
            return UpdaterResource(resolved(executable), "executable")
        main_script = source / "main.py"
        if main_script.is_file():
            return UpdaterResource(resolved(main_script), "python_script")
    raise UpdateApplyError(f"Updater source tidak ditemukan: {source}")


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _frozen_resource_root() -> Path:
    mei = getattr(sys, "_MEIPASS", None)
    if mei:
        return resolved(mei)
    return resolved(Path(sys.executable).parent)
