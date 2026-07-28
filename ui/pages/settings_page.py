"""Six-section central configuration Settings page for Sprint UI5B."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.pages.base_page import BasePage
from ui.pages.settings.configuration_section import ConfigurationSection
from ui.pages.settings.general_section import GeneralSection
from ui.pages.settings.module_configuration_section import (
    ModuleConfigurationSection,
)
from ui.pages.settings.recorder_profiles_section import RecorderProfilesSection
from ui.pages.settings.recovery_section import RecoverySection
from ui.pages.settings.storage_section import StorageSection
from ui.widgets import ProgressPanel


class SettingsPage(BasePage):
    page_id = "settings"
    title = "Settings"
    subtitle = "Konfigurasi aplikasi, penyimpanan, dan pemulihan."
    icon_name = "settings.ico"

    def __init__(self, parent, context) -> None:
        self._busy = False
        self._destructive_busy = False
        self._auto_refresh_started = False
        self._action_widgets: list[ttk.Widget] = []
        super().__init__(parent, context)

    def build_content(self) -> None:
        self.services = self.context.app_services
        if self.services is None:
            raise RuntimeError("Settings membutuhkan AppServices.")
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        sections = (
            ("General", GeneralSection),
            ("Module Configuration", ModuleConfigurationSection),
            ("Import / Export", ConfigurationSection),
            ("Storage & Database", StorageSection),
            ("Backup & Recovery", RecoverySection),
            ("HRIS Recorder Profiles", RecorderProfilesSection),
        )
        self.sections = {}
        for title, section_class in sections:
            section = section_class(self.notebook, self)
            self.notebook.add(section, text=title)
            self.sections[title] = section
        self.notebook.bind("<<NotebookTabChanged>>", self._section_selected)
        self.progress_panel = ProgressPanel(self)
        self.progress_panel.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.progress_panel.grid_remove()

    def _section_selected(self, _event=None) -> None:
        title = self.notebook.tab(self.notebook.select(), "text")
        section = self.sections.get(title)
        callback = getattr(section, "on_selected", None)
        if callable(callback):
            callback()

    def on_show(self) -> None:
        if self._auto_refresh_started or self._busy:
            return
        self._auto_refresh_started = True
        self._auto_refresh_startup_state()

    def _auto_refresh_startup_state(self) -> None:
        storage = self.sections.get("Storage & Database")
        if storage is None:
            return

        def done(status) -> None:
            storage.show_status(status)
            if status.database_valid and status.database_path is not None:
                self._auto_load_general(status.database_path)

        self.run_task(
            self.services.storage_service.resolve_status,
            on_success=done,
            message="Mengecek Storage & Database...",
        )

    def _auto_load_general(self, database) -> None:
        general = self.sections.get("General")
        if general is None:
            self._auto_load_modules(database)
            return

        def work():
            return (
                self.services.database_service.load_global_settings(database),
                self.services.database_service.load_module_global_usage(database),
                self.services.database_service.load_outlook_operational_settings(
                    database
                ),
            )

        def done(value) -> None:
            draft, usages, outlook = value
            general._loaded = draft
            general._apply(draft)
            general._show_usage(usages)
            general._apply_outlook(outlook)
            general.result.show_lines(["Global Settings otomatis dimuat."])
            self._auto_load_modules(database)

        self.run_task(
            work,
            on_success=done,
            message="Memuat Global Settings...",
        )

    def _auto_load_modules(self, database) -> None:
        module_section = self.sections.get("Module Configuration")
        if module_section is None:
            return
        self.run_task(
            lambda: self.services.module_configuration_service.load_summaries(
                database
            ),
            on_success=module_section._render,
            message="Memuat ringkasan konfigurasi modul...",
        )

    def show_configuration_section(
        self,
        *,
        module: str | None = None,
        export: bool = False,
    ) -> None:
        section = self.sections["Import / Export"]
        self.notebook.select(section)
        if module:
            section.select_advanced_module(module)
        section.focus_export() if export else section.focus_import()

    def register_action(self, widget: ttk.Widget) -> None:
        self._action_widgets.append(widget)

    def run_task(
        self,
        function,
        *,
        on_success,
        message: str,
        destructive: bool = False,
        cancellable: bool = True,
    ):
        if self._busy:
            self.services.dialog_service.warning(
                "Task sedang berjalan",
                "Tunggu operasi Settings saat ini selesai.",
            )
            return None
        self._set_busy(True, destructive=destructive, message=message)

        def finished(result) -> None:
            self._set_busy(False, destructive=False, message="")
            if result.success:
                on_success(result.value)
            else:
                self.context.logger.error("Settings task failed: %s", result.error)
                self.services.dialog_service.error(
                    "Operasi gagal",
                    result.error or "Terjadi kesalahan yang tidak diketahui.",
                )

        return self.services.task_runner.submit(
            function,
            on_done=finished,
            on_progress=lambda progress: self._set_status(progress.message),
            cancellable=cancellable,
        )

    def _set_busy(
        self,
        busy: bool,
        *,
        destructive: bool,
        message: str,
    ) -> None:
        self._busy = busy
        self._destructive_busy = busy and destructive
        live_widgets: list[ttk.Widget] = []
        for widget in self._action_widgets:
            try:
                if not widget.winfo_exists():
                    continue
                widget.configure(state="disabled" if busy else "normal")
            except tk.TclError:
                continue
            live_widgets.append(widget)
        self._action_widgets = live_widgets
        if busy:
            self.progress_panel.start(message)
            self._set_status(message)
        else:
            self.progress_panel.stop()
            self._set_status("Ready")

    def _set_status(self, message: str) -> None:
        if self.context.set_status is not None:
            self.context.set_status(message)

    def can_navigate_away(self) -> bool:
        return not self._destructive_busy

    @property
    def is_busy(self) -> bool:
        return self._busy
