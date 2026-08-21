"""Safe user-facing page factory error placeholder."""

from __future__ import annotations

from ui.context import AppContext
from ui.models import PageDefinition, PageLoadError
from ui.pages.base_page import BasePage
from ui.widgets import EmptyState


class ErrorPage(BasePage):
    page_id = "page_error"
    title = "Halaman tidak tersedia"
    subtitle = ""
    icon_name = "error.ico"

    def __init__(
        self,
        parent,
        context: AppContext,
        definition: PageDefinition,
        error: PageLoadError,
    ) -> None:
        self.definition = definition
        self.error = error
        self.title = definition.title
        super().__init__(parent, context)

    def build_content(self) -> None:
        EmptyState(
            self,
            title="Halaman gagal dibuka",
            message=(
                "Halaman ini belum dapat ditampilkan. Detail teknis telah "
                "dicatat pada log. Anda tetap dapat membuka menu lain."
            ),
        ).grid(row=1, column=0, sticky="nsew")
