"""Centralized, failure-tolerant icon loading for the Unified UI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

from config.app_config import ICON_PATH, PROJECT_ROOT
from shared.logger import get_logger

logger = get_logger(__name__)

ICON_FILES: dict[str, str] = {
    "app": "app.ico",
    "dashboard": "dashboard.ico",
    "attendance": "attendance.ico",
    "outlook_revisi": "outlook_revisi.ico",
    "hris": "hris.ico",
    "utilities": "utilities.ico",
    "history": "history.ico",
    "settings": "settings.ico",
    "system_health": "system_health.ico",
    "database": "database.ico",
    "info": "info.ico",
    "help": "help.ico",
    "comparison_result": "comparison_result.ico",
    "attachment_consolidation": "Attachment_Consolidation.ico",
}

REQUIRED_ICON_NAMES: tuple[str, ...] = tuple(ICON_FILES)


class IconManager:
    """Resolve and load project icons while retaining Tk image references."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        project_root: Path = PROJECT_ROOT,
    ) -> None:
        self.master = master
        self.project_root = project_root.resolve()
        self.icon_directory = self.project_root / ICON_PATH.relative_to(PROJECT_ROOT)
        self._cache: dict[tuple[str, int], ImageTk.PhotoImage | None] = {}

    def resolve(self, name: str) -> Path:
        """Return the configured path for an icon name."""

        filename = ICON_FILES.get(name)
        if filename is None:
            filename = Path(name).name
            if not Path(filename).suffix:
                filename = f"{filename}.ico"
        return self.icon_directory / filename

    def required_paths(self) -> dict[str, Path]:
        """Return all icon paths required by the Unified UI blueprint."""

        return {name: self.resolve(name) for name in REQUIRED_ICON_NAMES}

    def load(self, name: str, size: int = 24) -> ImageTk.PhotoImage | None:
        """Load an icon at the requested square size, or a safe fallback."""

        cache_key = (name, size)
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self.resolve(name)
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
                image = image.resize(
                    (size, size),
                    Image.Resampling.LANCZOS,
                )
            photo = ImageTk.PhotoImage(image, master=self.master)
        except Exception as error:
            logger.warning("Icon %s could not be loaded: %s", path, error)
            photo = self._create_fallback(size)

        self._cache[cache_key] = photo
        return photo

    def application_icon_path(self) -> Path:
        """Return the main multi-size application icon path."""

        return self.resolve("app")

    def _create_fallback(self, size: int) -> ImageTk.PhotoImage | None:
        try:
            image = Image.new("RGBA", (size, size), "#EAF3FF")
            draw = ImageDraw.Draw(image)
            inset = max(1, size // 8)
            draw.rounded_rectangle(
                (inset, inset, size - inset - 1, size - inset - 1),
                radius=max(2, size // 6),
                outline="#2F80ED",
                width=max(1, size // 12),
            )
            return ImageTk.PhotoImage(image, master=self.master)
        except Exception as error:
            logger.warning("Fallback icon could not be created: %s", error)
            return None
