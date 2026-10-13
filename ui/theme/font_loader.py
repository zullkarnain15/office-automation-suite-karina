"""Process-scoped font loading for the UI8 theme."""

from __future__ import annotations

import ctypes
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from tkinter import TclError
from tkinter import font as tkfont

from ui.theme.typography import RetroTypography, typography

FR_PRIVATE = 0x10
_LOADED_PRIVATE_FONT_PATHS: set[Path] = set()


@dataclass(frozen=True)
class FontLoadResult:
    attempted: tuple[Path, ...]
    loaded: tuple[Path, ...]
    missing: tuple[Path, ...]
    failed: tuple[Path, ...]
    ui_family: str
    display_family: str
    mono_family: str


def font_available(family: str, root=None) -> bool:
    try:
        return family in set(tkfont.families(root))
    except (RuntimeError, TclError, TypeError):
        return False


def _add_private_windows_font(path: Path) -> bool:
    add_font = ctypes.windll.gdi32.AddFontResourceExW
    add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    add_font.restype = ctypes.c_int
    return add_font(str(path), FR_PRIVATE, None) > 0


def load_private_font_files(
    paths: tuple[Path, ...],
    *,
    logger: logging.Logger | None = None,
) -> tuple[tuple[Path, ...], tuple[Path, ...], tuple[Path, ...]]:
    """Load font files for this process and return loaded/missing/failed paths.

    Windows uses ``FR_PRIVATE`` so no font is installed system-wide and no
    administrator access or Registry write is required. Successful paths are
    remembered to make repeated page construction and tests idempotent.
    """

    log = logger or logging.getLogger(__name__)
    loaded: list[Path] = []
    missing: list[Path] = []
    failed: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if not path.is_file():
            missing.append(path)
            continue
        if path in _LOADED_PRIVATE_FONT_PATHS:
            loaded.append(path)
            continue
        if sys.platform == "win32":
            try:
                if _add_private_windows_font(path):
                    _LOADED_PRIVATE_FONT_PATHS.add(path)
                    loaded.append(path)
                else:
                    failed.append(path)
            except (AttributeError, OSError) as exc:
                log.warning("Theme font failed to load: %s (%s)", path, exc)
                failed.append(path)
        else:
            # Non-Windows platforms cannot use the Windows private-font API.
            # Family resolution below still chooses an installed fallback.
            failed.append(path)
    return tuple(loaded), tuple(missing), tuple(failed)


def load_theme_fonts(
    *,
    spec: RetroTypography = typography,
    logger: logging.Logger | None = None,
) -> FontLoadResult:
    """Load bundled fonts for the current process only."""

    log = logger or logging.getLogger(__name__)
    attempted = spec.expected_files
    loaded, missing, failed = load_private_font_files(attempted, logger=log)

    ui_family = spec.ui_family if font_available(spec.ui_family) else spec.ui_fallback
    display_family = (
        spec.display_family
        if font_available(spec.display_family)
        else spec.display_fallback
    )
    mono_family = (
        spec.mono_family if font_available(spec.mono_family) else spec.mono_fallback
    )
    return FontLoadResult(
        attempted=attempted,
        loaded=loaded,
        missing=missing,
        failed=failed,
        ui_family=ui_family,
        display_family=display_family,
        mono_family=mono_family,
    )
