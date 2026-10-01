"""Base Frame used by all Unified UI placeholder pages."""

from __future__ import annotations

from tkinter import ttk

from unified_ui.icon_manager import IconManager


class BasePage(ttk.Frame):
    """Reusable page shell with title, description, and placeholder panel."""

    page_title = "Page"
    page_description = ""
    page_icon = "info"
    placeholder_text = "Integration is not active in Sprint U1."

    def __init__(
        self,
        parent: ttk.Frame,
        icon_manager: IconManager,
    ) -> None:
        super().__init__(parent, style="App.TFrame", padding=(28, 24))
        self.icon_manager = icon_manager
        self._page_icon = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_heading()
        self.build_content()

    def _build_heading(self) -> None:
        heading = ttk.Frame(self, style="App.TFrame")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        heading.columnconfigure(1, weight=1)

        self._page_icon = self.icon_manager.load(self.page_icon, 48)
        if self._page_icon is not None:
            ttk.Label(
                heading,
                image=self._page_icon,
                style="PageDescription.TLabel",
            ).grid(row=0, column=0, rowspan=2, padx=(0, 14))

        ttk.Label(
            heading,
            text=self.page_title,
            style="PageTitle.TLabel",
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            heading,
            text=self.page_description,
            style="PageDescription.TLabel",
        ).grid(row=1, column=1, sticky="w", pady=(4, 0))

    def build_content(self) -> None:
        """Build the standard Sprint U1 placeholder panel."""

        panel = ttk.Frame(self, style="Card.TFrame", padding=(28, 26))
        panel.grid(row=1, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)

        ttk.Label(
            panel,
            text="Sprint U1 • Unified UI Shell",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            panel,
            text=self.placeholder_text,
            style="CardText.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, sticky="nw", pady=(12, 0))
        ttk.Label(
            panel,
            text="Module integration is intentionally disabled.",
            style="CardStatus.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(18, 0))
