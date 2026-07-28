"""In-memory-only window state contract for future persistence."""

from __future__ import annotations

from dataclasses import dataclass

from ui.constants import WINDOW_HEIGHT, WINDOW_WIDTH


@dataclass(slots=True)
class WindowState:
    selected_page: str = "dashboard"
    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    maximized: bool = False

    def update_geometry(
        self,
        width: int,
        height: int,
        *,
        maximized: bool,
    ) -> None:
        if width > 0:
            self.width = width
        if height > 0:
            self.height = height
        self.maximized = maximized
