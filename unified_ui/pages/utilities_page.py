"""Utilities placeholder page with inactive subfeature cards."""

from __future__ import annotations

from tkinter import ttk

from unified_ui.pages.base_page import BasePage


class UtilitiesPage(BasePage):
    page_title = "Utilities"
    page_description = "Supporting tools for office automation workflows."
    page_icon = "utilities"

    def build_content(self) -> None:
        container = ttk.Frame(self, style="App.TFrame")
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1, uniform="utility")
        container.columnconfigure(1, weight=1, uniform="utility")
        container.rowconfigure(0, weight=1)

        features = (
            (
                "Comparison Result",
                "comparison_result",
                "Compare operational results in a guided workspace.",
            ),
            (
                "Attachment Consolidation",
                "attachment_consolidation",
                "Consolidate supported attachments into a structured result.",
            ),
        )

        for column, (title, icon_name, description) in enumerate(features):
            self._build_feature_card(
                container,
                column,
                title,
                icon_name,
                description,
            )

    def _build_feature_card(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        icon_name: str,
        description: str,
    ) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(26, 26))
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0, 10) if column == 0 else (10, 0),
        )
        card.columnconfigure(0, weight=1)

        image = self.icon_manager.load(icon_name, 64)
        if image is not None:
            ttk.Label(
                card,
                image=image,
                style="CardText.TLabel",
            ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            card,
            text=title,
            style="CardTitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(18, 0))
        ttk.Label(
            card,
            text=description,
            style="CardText.TLabel",
            wraplength=330,
            justify="left",
        ).grid(row=2, column=0, sticky="nw", pady=(10, 0))
        ttk.Label(
            card,
            text="Not connected in Sprint U1",
            style="CardStatus.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(20, 0))
