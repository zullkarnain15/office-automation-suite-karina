"""Main window composition and cached page navigation."""

from __future__ import annotations

import importlib
import tkinter as tk
from tkinter import ttk
from typing import Any

from config.app_config import APP_VERSION, WINDOW_TITLE
from shared.logger import get_logger
from unified_ui.icon_manager import IconManager
from unified_ui.pages import PAGE_BY_KEY, PAGE_REGISTRY, PageSpec
from unified_ui.theme import (
    ERROR,
    WINDOW_HEIGHT,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH,
    apply_theme,
)
from unified_ui.widgets import Header, Sidebar, StatusBar

logger = get_logger(__name__)


class MainWindow:
    """Single-window shell with lazy page creation and page caching."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._page_cache: dict[str, ttk.Frame] = {}
        self._active_page_key: str | None = None

        self._configure_root()
        apply_theme(root)
        self.icon_manager = IconManager(root)
        self._set_application_icon()
        self._build_layout()
        self.show_page("dashboard")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    @property
    def active_page_key(self) -> str | None:
        """Return the current navigation key."""

        return self._active_page_key

    @property
    def cached_page_keys(self) -> tuple[str, ...]:
        """Return keys for pages created during this session."""

        return tuple(self._page_cache)

    def _configure_root(self) -> None:
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.resizable(True, True)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

    def _set_application_icon(self) -> None:
        try:
            self.root.iconbitmap(self.icon_manager.application_icon_path())
        except Exception as error:
            logger.warning("Application icon could not be loaded: %s", error)

    def _build_layout(self) -> None:
        header = Header(self.root)
        header.grid(row=0, column=0, sticky="ew")

        body = ttk.Frame(self.root, style="App.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.content = ttk.Frame(body, style="App.TFrame")
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.sidebar = Sidebar(
            body,
            PAGE_REGISTRY,
            self.icon_manager,
            self.show_page,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        self.status_bar = StatusBar(self.root, APP_VERSION)
        self.status_bar.grid(row=2, column=0, sticky="ew")

    def show_page(self, page_key: str) -> None:
        """Show one cached page and hide the previously active page."""

        spec = PAGE_BY_KEY.get(page_key)
        if spec is None:
            logger.error("Unknown Unified UI page requested: %s", page_key)
            self.status_bar.set_status("Navigation unavailable")
            return

        if self._active_page_key == page_key:
            return

        if self._active_page_key is not None:
            active_page = self._page_cache.get(self._active_page_key)
            if active_page is not None:
                active_page.grid_remove()

        page = self._page_cache.get(page_key)
        if page is None:
            page = self._create_page(spec)
            self._page_cache[page_key] = page

        page.grid(row=0, column=0, sticky="nsew")
        page.tkraise()
        self._active_page_key = page_key
        self.sidebar.select(page_key)
        self.status_bar.set_status(f"Ready • {spec.title}")
        logger.info("Unified UI page selected: %s", page_key)

    def _create_page(self, spec: PageSpec) -> ttk.Frame:
        try:
            module = importlib.import_module(spec.module_name)
            page_class: Any = getattr(module, spec.class_name)
            return page_class(self.content, self.icon_manager)
        except Exception as error:
            logger.exception("Unified UI page failed to load: %s", spec.key)
            return self._build_error_page(spec, error)

    def _build_error_page(
        self,
        spec: PageSpec,
        error: Exception,
    ) -> ttk.Frame:
        frame = ttk.Frame(
            self.content,
            style="App.TFrame",
            padding=(28, 24),
        )
        frame.columnconfigure(0, weight=1)
        ttk.Label(
            frame,
            text=f"{spec.title} could not be displayed.",
            style="PageTitle.TLabel",
            foreground=ERROR,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text=(
                "The shell is still available. Details were written to "
                f"the application log.\n\n{error}"
            ),
            style="PageDescription.TLabel",
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, sticky="nw", pady=(12, 0))
        return frame

    def close(self) -> None:
        """Close the Tk application cleanly."""

        logger.info("Closing OAS-K Unified UI shell.")
        self.root.destroy()
