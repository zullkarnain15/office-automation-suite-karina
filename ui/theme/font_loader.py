"""Process-scoped font loading for the UI8 theme."""

from __future__ import annotations

import ctypes
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from tkinter import font as tkfont

from ui.theme.typography import RetroTypography, typography

FR_PRIVATE = 0x10


@dataclass(frozen=True)
class FontLoadResult:
    attempted: tuple[Path, ...]
    loaded: tuple[Path, ...]
    missing: tuple[Path, ...]
    failed: tuple[Path, ...]
    ui_family: str
    display_family: str
    mono_family: str


def _font_available(family: str) -> bool:
    try:
        return family in set(tkfont.families())
    except RuntimeError:
        return False


def _add_private_windows_font(path: Path) -> bool:
    add_font = ctypes.windll.gdi32.AddFontResourceExW
    add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    add_font.restype = ctypes.c_int
    return add_font(str(path), FR_PRIVATE, None) > 0


def load_theme_fonts(
    *,
    spec: RetroTypography = typography,
    logger: logging.Logger | None = None,
) -> FontLoadResult:
    """Load bundled fonts for the current process only."""

    log = logger or logging.getLogger(__name__)
    attempted = spec.expected_files
    loaded: list[Path] = []
    missing: list[Path] = []
    failed: list[Path] = []

    for path in attempted:
        if not path.is_file():
            missing.append(path)
            continue
        if sys.platform == "win32":
            try:
                if _add_private_windows_font(path):
                    loaded.append(path)
                else:
                    failed.append(path)
            except (AttributeError, OSError) as exc:
                log.warning("Theme font failed to load: %s (%s)", path, exc)
                failed.append(path)
        else:
            loaded.append(path)

    ui_family = spec.ui_family if _font_available(spec.ui_family) else spec.ui_fallback
    display_family = (
        spec.display_family
        if _font_available(spec.display_family)
        else spec.display_fallback
    )
    mono_family = (
        spec.mono_family if _font_available(spec.mono_family) else spec.mono_fallback
    )
    return FontLoadResult(
        attempted=attempted,
        loaded=tuple(loaded),
        missing=tuple(missing),
        failed=tuple(failed),
        ui_family=ui_family,
        display_family=display_family,
        mono_family=mono_family,
    )
