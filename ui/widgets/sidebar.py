"""Icon-led, keyboard-focusable sidebar navigation."""

from __future__ import annotations

from collections.abc import Callable
from tkinter import ttk

from ui.constants import OLD_GOLD
from ui.icon_manager import IconManager
from ui.page_registry import PageRegistry


class Sidebar(ttk.Frame):
    def __init__(
        self,
        parent,
        registry: PageRegistry,
        icon_manager: IconManager,
        command: Callable[[str], bool],
        *,
        application_version: str,
    ) -> None:
        super().__init__(
            parent,
            style="Sidebar.TFrame",
            padding=(6, 12),
        )
        self.registry = registry
        self.icon_manager = icon_manager
        self.command = command
        self._buttons: dict[str, ttk.Button] = {}
        self._markers: dict[str, ttk.Label] = {}
        self._images: dict[str, object] = {}
        self.columnconfigure(1, weight=1)
        self.rowconfigure(9, weight=1)

        ttk.Label(self, text="OAS-K", style="SidebarBrand.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 10)
        )

        for row, definition in enumerate(registry, start=1):
            image = icon_manager.load(definition.icon_name, size=20)
            marker = ttk.Label(self, text="", style="SidebarCaption.TLabel", width=1)
            marker.grid(row=row, column=0, sticky="ns")
            button = ttk.Button(
                self,
                text=definition.title,
                image=image,
                compound="left",
                style="Sidebar.TButton",
                takefocus=True,
                command=lambda page_id=definition.page_id: self.command(page_id),
            )
            button.grid(row=row, column=1, sticky="ew")
            self._buttons[definition.page_id] = button
            self._markers[definition.page_id] = marker
            if image is not None:
                self._images[definition.page_id] = image

        ttk.Label(
            self,
            text=f"Versi {application_version}",
            style="SidebarCaption.TLabel",
        ).grid(
            row=10,
            column=0,
            columnspan=2,
            sticky="sw",
            padx=8,
            pady=(10, 0),
        )

    def set_active(self, page_id: str) -> None:
        for item_id, button in self._buttons.items():
            active = item_id == page_id
            button.configure(
                style="SidebarActive.TButton" if active else "Sidebar.TButton"
            )
            self._markers[item_id].configure(
                text="|" if active else "",
                foreground=OLD_GOLD,
            )

    @property
    def menu_ids(self) -> tuple[str, ...]:
        return tuple(self._buttons)
