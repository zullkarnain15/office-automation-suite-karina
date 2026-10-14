"""Central UI8 typography tokens with safe fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.app_config import PROJECT_ROOT


@dataclass(frozen=True)
class RetroTypography:
    font_dir: Path = PROJECT_ROOT / "assets" / "fonts"
    silkscreen_regular_file: str = "Silkscreen-Regular.ttf"
    silkscreen_bold_file: str = "Silkscreen-Bold.ttf"
    press_start_file: str = "PressStart2P-Regular.ttf"
    vt323_file: str = "VT323-Regular.ttf"
    ui_family: str = "Silkscreen"
    ui_fallback: str = "Segoe UI"
    display_family: str = "Press Start 2P"
    display_fallback: str = "Segoe UI"
    mono_family: str = "VT323"
    mono_fallback: str = "Consolas"

    @property
    def expected_files(self) -> tuple[Path, ...]:
        return (
            self.font_dir / self.silkscreen_regular_file,
            self.font_dir / self.silkscreen_bold_file,
            self.font_dir / self.press_start_file,
            self.font_dir / self.vt323_file,
        )


typography = RetroTypography()
