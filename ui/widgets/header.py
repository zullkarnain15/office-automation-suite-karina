"""Page title, subtitle, and lightweight application status header."""

from __future__ import annotations

from tkinter import ttk

from ui.icon_manager import IconManager
from ui.models import HeaderMetadata


class Header(ttk.Frame):
    def __init__(self, parent, icon_manager: IconManager | None = None) -> None:
        super().__init__(
            parent,
            style="Header.TFrame",
            padding=(24, 12),
        )
        self._title_icons = self._load_title_icons(icon_manager)
        self.columnconfigure(1, weight=1)
        self.actions = ttk.Frame(self, style="Header.TFrame")
        self.actions.grid(row=0, column=2, rowspan=2, padx=(16, 20))
        self.title_icon_label = ttk.Label(
            self,
            style="Header.TLabel",
        )
        self.title_label = ttk.Label(
            self,
            text="",
            style="PageTitle.TLabel",
        )
        self.title_label.grid(row=0, column=1, sticky="w")
        self.subtitle_label = ttk.Label(
            self,
            text="",
            style="PageSubtitle.TLabel",
        )
        self.subtitle_label.grid(row=1, column=1, sticky="w", pady=(3, 0))
        self.status_label = ttk.Label(
            self,
            text="STATUS APLIKASI: Siap",
            style="HeaderStatus.TLabel",
        )
        self.status_label.grid(row=0, column=3, rowspan=2, sticky="e")

    def update_metadata(self, metadata: HeaderMetadata) -> None:
        self.title_label.configure(text=metadata.title)
        self.subtitle_label.configure(text=metadata.subtitle)
        icon = self._title_icons.get(metadata.title.casefold())
        if icon is not None:
            self.title_icon_label.configure(image=icon)
            self.title_icon_label.grid(
                row=0,
                column=0,
                rowspan=2,
                sticky="w",
                padx=(0, 12),
            )
        else:
            self.title_icon_label.grid_remove()
        self.status_label.configure(
            text=f"STATUS APLIKASI: {metadata.application_status}"
        )

    @staticmethod
    def _load_title_icons(
        icon_manager: IconManager | None,
    ) -> dict[str, object]:
        if icon_manager is None:
            return {}
        icon_names = {
            "dashboard": "mob_icon.png",
            "attendance": "jamur.png",
            "outlook revisi": "blue_slime.png",
            "hris": "green_slime.png",
            "utilities": "red_apple.png",
            "history": "history_wizard.png",
            "settings": "setting_stick.png",
            "system health": "sys_healt.png",
        }
        return {
            title: icon
            for title, icon_name in icon_names.items()
            if (icon := icon_manager.load(icon_name, size=32)) is not None
        }
