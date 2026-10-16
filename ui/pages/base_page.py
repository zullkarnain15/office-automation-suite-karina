"""Lifecycle contract shared by all unified UI pages."""

from __future__ import annotations

from tkinter import ttk

from ui.context import AppContext
from ui.widgets import EmptyState, SectionHeader


class BasePage(ttk.Frame):
    page_id = "base"
    title = "Halaman"
    subtitle = ""
    icon_name = "info.ico"
    show_page_heading = True

    def __init__(self, parent, context: AppContext) -> None:
        self._module_job_id: str | None = None
        super().__init__(
            parent,
            style="OASK.TFrame",
            padding=(24, 12),
        )
        self.context = context
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        if self.show_page_heading:
            SectionHeader(self, self.title).grid(
                row=0,
                column=0,
                sticky="w",
                pady=(0, 14),
            )
        self.build_content()

    def build_content(self) -> None:
        EmptyState(
            self,
            title=self.title,
            message=(
                f"{self.subtitle}\n\n"
                "Integrasi modul akan ditambahkan pada sprint berikutnya."
            ),
        ).grid(row=1, column=0, sticky="nsew")

    def on_show(self) -> None:
        """Called after the page becomes visible."""

    def on_hide(self) -> None:
        """Called before navigation away from this page."""

    def refresh(self) -> None:
        """Refresh lightweight page state; no-op during UI1."""

    def can_navigate_away(self) -> bool:
        return True

    def can_close(self) -> bool:
        return self.can_navigate_away()

    def _begin_module_job(
        self,
        module: str,
        title: str,
        *,
        resources=(),
        read_paths=(),
        write_paths=(),
        exclusive: bool = False,
    ) -> bool:
        coordinator = getattr(
            getattr(self.context, "app_services", None),
            "module_job_coordinator",
            None,
        )
        if coordinator is None:
            return True
        result = coordinator.try_start(
            module,
            title,
            resources=resources,
            read_paths=read_paths,
            write_paths=write_paths,
            exclusive=exclusive,
        )
        if not result.accepted:
            self.context.app_services.dialog_service.warning(
                "Job tidak dapat dimulai", result.message
            )
            return False
        self._module_job_id = result.job.job_id
        return True

    def _finish_module_job(self) -> None:
        job_id = getattr(self, "_module_job_id", None)
        coordinator = getattr(
            getattr(self.context, "app_services", None),
            "module_job_coordinator",
            None,
        )
        if coordinator is not None:
            coordinator.finish(job_id)
        self._module_job_id = None

    def dispose(self) -> None:
        """Release page-owned resources; pages own none during UI1."""
