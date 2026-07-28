"""Storage-only HRIS recorder profile section."""

from __future__ import annotations

from pathlib import Path
from tkinter import ttk

from ui.pages.settings.common import SettingsSection
from ui.widgets import ResultSummary


class RecorderProfilesSection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        self.selected_reference: Path | None = None
        ttk.Label(
            self,
            text="HRIS Recorder Profiles",
            style="SectionHeader.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.table = ttk.Treeview(
            self,
            columns=("filename", "relative", "modified", "valid"),
            show="headings",
            height=8,
        )
        for column, title in (
            ("filename", "Filename"),
            ("relative", "Relative Path"),
            ("modified", "Modified"),
            ("valid", "Valid"),
        ):
            self.table.heading(column, text=title)
            self.table.column(column, width=180, stretch=True)
        self.table.grid(row=1, column=0, sticky="nsew", pady=8)
        self.table.bind("<<TreeviewSelect>>", self._selected)
        buttons = ttk.Frame(self, style="OASK.TFrame")
        buttons.grid(row=2, column=0, sticky="w")
        actions = (
            ("Refresh", self.refresh),
            ("Import Profile JSON", self.import_profile),
            ("Validate Profile", self.validate_profile),
            ("Open Profile Folder", self.open_folder),
            ("Remove Reference", self.remove_reference),
        )
        for index, (text, command) in enumerate(actions):
            button = ttk.Button(buttons, text=text, command=command)
            button.grid(row=0, column=index, padx=4)
            self.page.register_action(button)
        self.result = ResultSummary(self)
        self.result.grid(row=3, column=0, sticky="ew", pady=(10, 0))

    def refresh(self) -> None:
        root = self.active_data_root()
        self.page.run_task(
            lambda: self.services.recorder_profile_service.list_profiles(root),
            on_success=self._show_profiles,
            message="Membaca recorder profiles...",
        )

    def _show_profiles(self, values) -> None:
        self.table.delete(*self.table.get_children())
        for value in values:
            self.table.insert(
                "",
                "end",
                values=(
                    value.filename,
                    str(value.relative_path),
                    value.modified_at,
                    "Ya" if value.valid else "Tidak",
                ),
            )
        self.result.show_lines([f"Recorder profiles: {len(values)}"])

    def import_profile(self) -> None:
        source = self.services.dialog_service.select_file(
            title="Pilih Recorder Profile JSON",
            filetypes=(("JSON", "*.json"),),
        )
        if source is None:
            return
        root = self.active_data_root()
        target = (
            self.active_status().recorder_profiles_folder / source.name
            if self.active_status().recorder_profiles_folder
            else None
        )
        overwrite = False
        if target is not None and target.exists():
            overwrite = self.services.dialog_service.confirm(
                "Duplicate Recorder Profile",
                "Filename sudah ada. Timpa setelah validasi?",
            )
            if not overwrite:
                return
        self.page.run_task(
            lambda: self.services.recorder_profile_service.import_profile(
                source, root, overwrite=overwrite
            ),
            on_success=lambda relative: (
                self.result.show_lines([f"Imported: {relative}"]),
                self.refresh(),
            ),
            message="Mengimpor recorder profile...",
        )

    def validate_profile(self) -> None:
        if self.selected_reference is None:
            self.services.dialog_service.warning(
                "Validate Profile", "Pilih profile terlebih dahulu."
            )
            return
        root = self.active_data_root()
        result = self.services.recorder_profile_service.validate(
            root, self.selected_reference
        )
        self.result.show_lines(
            [
                f"Exists: {result.exists}",
                f"Readable: {result.readable}",
                f"JSON Object: {result.json_object_valid}",
                *(result.warnings or ()),
                *(result.errors or ()),
            ]
        )

    def open_folder(self) -> None:
        folder = self.active_status().recorder_profiles_folder
        if folder is None or not self.services.file_system_service.open_folder(folder):
            self.services.dialog_service.warning(
                "Open Profile Folder", str(folder or "Belum tersedia")
            )

    def remove_reference(self) -> None:
        if self.selected_reference is None:
            return
        value = self.services.recorder_profile_service.remove_reference(
            self.selected_reference
        )
        self.selected_reference = None
        self.result.show_lines(
            [
                f"Reference dilepas dari pilihan UI: {value}",
                "File tidak dihapus.",
            ]
        )

    def _selected(self, event) -> None:
        selection = self.table.selection()
        if selection:
            values = self.table.item(selection[0], "values")
            self.selected_reference = Path(values[1])
