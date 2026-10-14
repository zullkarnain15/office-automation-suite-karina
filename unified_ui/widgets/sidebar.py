"""Left navigation sidebar widget."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from tkinter import ttk

from unified_ui.icon_manager import IconManager
from unified_ui.pages import PageSpec


class Sidebar(ttk.Frame):
    """Sidebar with active navigation highlighting."""

    def __init__(
        self,
        parent: ttk.Frame,
        pages: Sequence[PageSpec],
        icon_manager: IconManager,
        on_select: Callable[[str], None],
    ) -> None:
        super().__init__(parent, style="Sidebar.TFrame", padding=(12, 18))
        self._buttons: dict[str, ttk.Button] = {}
        self.columnconfigure(0, weight=1)

        ttk.Label(
            self,
            text="NAVIGATION",
            style="SidebarTitle.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(0, 10))

        for row, page in enumerate(pages, start=1):
            image = icon_manager.load(page.icon_name, 22)
            options: dict[str, object] = {
                "text": page.title,
                "style": "Navigation.TButton",
                "command": lambda key=page.key: on_select(key),
            }
            if image is not None:
                options["image"] = image
                options["compound"] = "left"

            button = ttk.Button(self, **options)
            button.grid(row=row, column=0, sticky="ew", pady=1)
            self._buttons[page.key] = button

        self.rowconfigure(len(pages) + 1, weight=1)

    def select(self, page_key: str) -> None:
        """Apply selected styling to one navigation button."""

        for key, button in self._buttons.items():
            style = (
                "Selected.Navigation.TButton"
                if key == page_key
                else "Navigation.TButton"
            )
            button.configure(style=style)
