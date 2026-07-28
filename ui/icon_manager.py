"""Lazy Tk icon loading with safe text-only fallback."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk


class IconManager:
    def __init__(
        self,
        icons_path: str | Path,
        *,
        master: tk.Misc | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.icons_path = Path(icons_path)
        self.master = master
        self.logger = logger or logging.getLogger(__name__)
        self._cache: dict[
            tuple[str, int | tuple[int, int] | None],
            tk.PhotoImage | None,
        ] = {}

    def resolve(self, icon_name: str) -> Path:
        safe_name = Path(icon_name).name
        if not safe_name:
            raise ValueError("icon_name must not be empty.")
        return self.icons_path / safe_name

    def exists(self, icon_name: str) -> bool:
        return self.resolve(icon_name).is_file()

    def load(
        self,
        icon_name: str,
        *,
        size: int | tuple[int, int] | None = None,
    ) -> tk.PhotoImage | None:
        """Load supported Tk image formats or return a text-only fallback."""

        cache_key = (icon_name, size)
        if cache_key in self._cache:
            return self._cache[cache_key]
        path = self.widget_icon_path(icon_name)
        if not path.is_file():
            self.logger.warning("UI icon is missing: %s", path)
            self._cache[cache_key] = None
            return None
        try:
            if size is None:
                image = tk.PhotoImage(master=self.master, file=str(path))
            else:
                image = self._load_scaled_png(path, size)
        except (tk.TclError, OSError, RuntimeError) as exc:
            self.logger.warning(
                "UI icon cannot be used by Tk; text fallback enabled: %s (%s)",
                path,
                exc,
            )
            image = None
        self._cache[cache_key] = image
        return image

    def _load_scaled_png(
        self,
        path: Path,
        size: int | tuple[int, int],
    ) -> tk.PhotoImage:
        target_size = (size, size) if isinstance(size, int) else size
        with Image.open(path) as source:
            image = source.convert("RGBA")
            if image.size != target_size:
                image = image.resize(target_size, Image.Resampling.NEAREST)
            return ImageTk.PhotoImage(image, master=self.master)

    def widget_icon_path(self, icon_name: str) -> Path:
        source = self.resolve(icon_name)
        if source.suffix.casefold() == ".ico":
            return self.icons_path / "png" / f"{source.stem}.png"
        return source

    def application_icon_path(self) -> Path | None:
        path = self.resolve("app.ico")
        return path if path.is_file() else None

    @property
    def cached_icon_names(self) -> tuple[str, ...]:
        return tuple(name for name, _size in self._cache)

    def clear(self) -> None:
        self._cache.clear()
