"""Simple Select -> Review -> Apply workflow, separate from export."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import MAIN_BACKGROUND
from ui.dialogs.configuration_review_dialog import ConfigurationReviewDialog
from ui.pages.settings.common import SettingsSection
from ui.widgets import ModernCard, ResultSummary, StepIndicator


class ConfigurationSection(SettingsSection):
    MODULES = ("GLOBAL", "ATTENDANCE", "OUTLOOK_REVISI", "HRIS", "UTILITIES")

    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        self.preview = None
        self.source_file = None
        self.global_resolution = None
        self.module_vars: dict[str, tk.BooleanVar] = {}
        self.advanced_var = tk.BooleanVar(value=False)
        self.selected_only_var = tk.BooleanVar(value=False)
        self.risk_confirmed = tk.BooleanVar(value=False)
        self.last_export_path = None

        ttk.Label(self, text="Import / Export", style="SectionHeader.TLabel").grid(row=0, column=0, sticky="w")
        viewport = ttk.Frame(self, style="OASK.TFrame")
        viewport.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        canvas = tk.Canvas(
            viewport,
            highlightthickness=0,
            background=MAIN_BACKGROUND,
        )
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        cards = ttk.Frame(canvas, style="OASK.TFrame")
        window = canvas.create_window((0, 0), window=cards, anchor="nw")
        cards.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        cards.columnconfigure((0, 1), weight=1, uniform="configuration-card")
        self.import_card = ModernCard(cards, title="Import Konfigurasi")
        self.export_card = ModernCard(cards, title="Export Konfigurasi")
        self.import_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.export_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_import()
        self._build_export()

    def _build_import(self) -> None:
        card = self.import_card.body
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="Gunakan satu workbook unified: pilih, periksa, lalu terapkan.", wraplength=390).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.steps = StepIndicator(
            card,
            ("Pilih File", "Periksa", "Terapkan"),
        )
        self.steps.grid(row=1, column=0, sticky="w", pady=(0, 10))
        ttk.Label(card, text="1 — Pilih File", style="CardTitle.TLabel").grid(row=2, column=0, sticky="w")
        self.file_status = ttk.Label(card, text="File Konfigurasi OAS-K belum dipilih.", wraplength=390)
        self.file_status.grid(row=3, column=0, sticky="w", pady=4)
        self.select_button = ttk.Button(card, text="Pilih File Excel", command=self.select_file)
        self.select_button.grid(row=4, column=0, sticky="w")
        ttk.Label(card, text="2 — Periksa Konfigurasi", style="CardTitle.TLabel").grid(row=5, column=0, sticky="w", pady=(12, 4))
        self.review_button = ttk.Button(card, text="Periksa Konfigurasi", command=self.build_preview, state="disabled")
        self.review_button.grid(row=6, column=0, sticky="w")
        self.import_result = ResultSummary(card)
        self.import_result.grid(row=7, column=0, sticky="ew", pady=8)

        self.advanced_check = ttk.Checkbutton(card, text="Pengaturan Lanjutan", variable=self.advanced_var, command=self._toggle_advanced)
        self.advanced_check.grid(row=8, column=0, sticky="w")
        self.advanced_frame = ttk.LabelFrame(card, text="Pilih Modul", padding=8)
        self.selected_only_check = ttk.Checkbutton(self.advanced_frame, text="Hanya perbarui modul tertentu", variable=self.selected_only_var, command=self._toggle_module_choices)
        self.selected_only_check.grid(row=0, column=0, sticky="w")
        self.module_frame = ttk.Frame(self.advanced_frame)
        self.module_frame.grid(row=1, column=0, sticky="w", pady=(4, 0))
        for row, module in enumerate(self.MODULES):
            variable = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                self.module_frame,
                text=self._module_label(module),
                variable=variable,
                command=self._update_apply_state,
            ).grid(row=row, column=0, sticky="w")
            self.module_vars[module] = variable
        self.module_frame.grid_remove()
        self.advanced_frame.grid_remove()

        ttk.Label(card, text="3 — Terapkan Konfigurasi", style="CardTitle.TLabel").grid(row=10, column=0, sticky="w", pady=(12, 4))
        self.confirm_box = ttk.Checkbutton(card, text="Saya telah memeriksa peringatan dan data yang akan diganti atau dihapus", variable=self.risk_confirmed, command=self._update_apply_state)
        self.confirm_box.grid(row=11, column=0, sticky="w")
        actions = ttk.Frame(card, style="ContentCard.TFrame")
        actions.grid(row=12, column=0, sticky="w", pady=(6, 0))
        self.detail_button = ttk.Button(actions, text="Lihat Detail", command=self.show_detail, state="disabled")
        self.detail_button.pack(side="left", padx=(0, 6))
        self.apply_button = ttk.Button(actions, text="Terapkan Konfigurasi", style="Primary.TButton", command=self.commit_preview, state="disabled")
        self.apply_button.pack(side="left")
        for widget in (self.select_button, self.review_button, self.detail_button, self.apply_button):
            self.page.register_action(widget)

    def _build_export(self) -> None:
        card = self.export_card.body
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="Export selalu menghasilkan satu workbook unified.", wraplength=390).grid(row=0, column=0, sticky="w", pady=(0, 10))
        for row, (text, command) in enumerate((("Export Konfigurasi Aktif", self.export_current), ("Simpan Template Kosong", self.save_template_copy), ("Buka Folder Template", self.open_template_folder), ("Buka Folder Hasil", self.open_export_folder)), start=2):
            button = ttk.Button(card, text=text, command=command)
            button.grid(row=row, column=0, sticky="w", pady=3)
            self.page.register_action(button)
        self.export_result = ResultSummary(card)
        self.export_result.grid(row=6, column=0, sticky="ew", pady=(10, 0))

    def select_file(self) -> None:
        source = self.services.dialog_service.select_file(title="Pilih File Konfigurasi OAS-K", filetypes=(("Excel Workbook", "*.xlsx"),))
        if source is None:
            return
        try:
            detected = self.services.configuration_service.inspect_file(source)
        except Exception as exc:
            self.source_file = None
            self.file_status.configure(text=f"File tidak valid: {exc}")
            self.review_button.configure(state="disabled")
            return
        self.source_file = source
        self.preview = None
        self.global_resolution = None
        self.risk_confirmed.set(False)
        detected_modules = {
            "OAS_K_UNIFIED": "Global Settings, Attendance, Outlook Revisi, HRIS, Utilities",
            "ATTENDANCE_LEGACY": "Attendance (fallback legacy)",
            "OUTLOOK_REVISI_LEGACY": "Outlook Revisi (fallback legacy)",
            "HRIS_LEGACY": "HRIS (fallback legacy)",
        }.get(detected.identity.value, "Tidak dikenali")
        valid = detected.identity.value not in {"UNKNOWN", "AMBIGUOUS"}
        self.file_status.configure(
            text=(
                f"{source.name}\nJenis: {detected.identity.value}\n"
                f"Modul: {detected_modules}\n"
                f"Status: {'Valid untuk diperiksa' if valid else 'Tidak valid'}"
            )
        )
        self.review_button.configure(state="normal" if valid else "disabled")
        self.steps.set_step(1 if valid else 0)
        self.detail_button.configure(state="disabled")
        self._update_apply_state()

    def build_preview(self) -> None:
        if self.source_file is None:
            self.services.dialog_service.warning("Import Konfigurasi", "Pilih file Excel terlebih dahulu.")
            return
        database = self._require_active_database("Periksa Konfigurasi")
        if database is None:
            return
        def done(preview) -> None:
            self.preview = preview
            summary = self.services.configuration_service.present_preview(preview)
            self._show_summary(summary)
            self.detail_button.configure(state="normal")
            self._update_apply_state()
            self.steps.set_step(2 if preview.can_commit else 1)
            if {item.code for item in preview.issues} & {"GLOBAL_OUTPUT_CONFLICT", "GLOBAL_PERIOD_CONFLICT"}:
                self.resolve_global_conflict()
        self.page.run_task(lambda: self.services.configuration_service.preview(database, (self.source_file,), global_resolution=self.global_resolution), on_success=done, message="Memeriksa konfigurasi...")

    def resolve_global_conflict(self) -> None:
        if self.preview is None:
            return
        conflicts = [item for item in self.preview.issues if item.code in {"GLOBAL_OUTPUT_CONFLICT", "GLOBAL_PERIOD_CONFLICT"}]
        if not conflicts:
            return
        resolution = dict(self.global_resolution or {})
        for issue in conflicts:
            choice = self.services.dialog_service.prompt_text(
                "Pilih Nilai yang Digunakan",
                f"{self.services.configuration_service._issue_text(issue.code, issue.message)[0]}\n\nNilai aktif: {issue.current_value}\nNilai dari file: {issue.proposed_value}\n\nKetik AKTIF, FILE, atau nilai lain:",
            )
            if not choice:
                return
            selected = issue.current_value if choice.strip().upper() == "AKTIF" else issue.proposed_value if choice.strip().upper() == "FILE" else choice.strip()
            if issue.code == "GLOBAL_OUTPUT_CONFLICT":
                resolution["output_root"] = selected
            else:
                values = selected if isinstance(selected, (tuple, list)) else str(selected).replace(" / ", ",").split(",")
                if len(values) != 2:
                    self.services.dialog_service.warning("Pilih Nilai yang Digunakan", "Periode alternatif harus: YYYY-MM-DD,YYYY-MM-DD")
                    return
                resolution.update(period_start=str(values[0]).strip(), period_end=str(values[1]).strip())
        self.global_resolution = resolution
        self.build_preview()

    def commit_preview(self) -> None:
        if self.preview is None or not self.preview.can_commit:
            self.services.dialog_service.warning("Terapkan Konfigurasi", "Hasil pemeriksaan yang valid wajib tersedia.")
            return
        modules = self._selected_modules()
        if not modules:
            self.services.dialog_service.warning("Terapkan Konfigurasi", "Pilih minimal satu modul pada Pengaturan Lanjutan.")
            return
        if self.preview.confirmation_required and not self.risk_confirmed.get():
            self.services.dialog_service.warning("Terapkan Konfigurasi", "Persetujuan wajib dicentang sebelum menerapkan.")
            return
        summary = self.services.configuration_service.present_preview(self.preview)
        message = "Modul: " + ", ".join(modules) + f"\nData diperbarui: {summary.update_count}\nData ditambahkan: {summary.insert_count}\nData dihapus: {summary.delete_count}\nPeringatan: {summary.warning_count}\n\nTerapkan sekarang?"
        if not self.services.dialog_service.confirm("Terapkan Sekarang", message):
            return
        database = self._require_active_database("Terapkan Konfigurasi")
        if database is None:
            return
        def work():
            result = self.services.configuration_service.commit_preview(
                database,
                self.preview,
                modules=modules,
                confirmed=True,
            )
            summaries = self.services.module_configuration_service.load_summaries(
                database
            )
            globals_value = self.services.database_service.load_global_settings(
                database
            )
            usages = self.services.database_service.load_module_global_usage(database)
            return result, summaries, globals_value, usages

        def done(value) -> None:
            result, summaries, globals_value, usages = value
            self.steps.set_step(3)
            self.import_result.show_lines(["Penerapan selesai.", *(f"{item.module}: {'Berhasil' if item.committed else 'Gagal'} ({item.changes_applied} perubahan)" for item in result.module_results)])
            module_section = self.page.sections.get("Module Configuration")
            if module_section:
                module_section._render(summaries)
            general = self.page.sections.get("General")
            if general:
                general._loaded = globals_value
                general._apply(globals_value)
                general._show_usage(usages)
        self.page.run_task(work, on_success=done, message="Menerapkan konfigurasi...", destructive=True, cancellable=False)

    def show_detail(self) -> None:
        if self.preview is not None:
            ConfigurationReviewDialog(self, self.preview, self.services.configuration_service.present_preview(self.preview))

    def export_current(self) -> None:
        target = self.services.dialog_service.save_file(title="Export Konfigurasi Aktif", default_name=self.services.configuration_service.default_export_name(), filetypes=(("Excel Workbook", "*.xlsx"),))
        if target is None:
            return
        overwrite = target.exists() and self.services.dialog_service.confirm("Timpa File", f"File sudah ada:\n{target}\n\nTimpa file?")
        if target.exists() and not overwrite:
            return
        database = self._require_active_database("Export Konfigurasi")
        if database is None:
            return
        def done(result) -> None:
            self.last_export_path = result.output_path
            digest = self.services.configuration_service.file_sha256(result.output_path)
            self.export_result.show_lines([f"File: {result.output_path}", f"Ukuran: {result.output_path.stat().st_size} bytes", f"SHA-256: {digest}", "Valid: Ya" if result.validation.is_valid else "Valid: Tidak"])
        self.page.run_task(lambda: self.services.configuration_service.export(database, target, overwrite=overwrite), on_success=done, message="Mengekspor konfigurasi...")

    def save_template_copy(self) -> None:
        target = self.services.dialog_service.save_file(title="Simpan Template Kosong", default_name="OAS-K_Configuration_Template.xlsx", filetypes=(("Excel Workbook", "*.xlsx"),))
        if target is None:
            return
        overwrite = target.exists() and self.services.dialog_service.confirm("Timpa Template", "File tujuan sudah ada. Timpa?")
        if target.exists() and not overwrite:
            return
        self.page.run_task(lambda: self.services.configuration_service.save_template_copy(target, overwrite=overwrite), on_success=lambda path: self.export_result.show_lines([f"Template tersimpan: {path}"]), message="Menyalin template kosong...")

    def open_template_folder(self) -> None:
        path = self.services.configuration_service.template_path.parent
        if not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning("Folder Template", str(path))

    def open_export_folder(self) -> None:
        path = self.last_export_path
        if path is None or not self.services.file_system_service.open_folder(path):
            self.services.dialog_service.warning(
                "Folder Hasil", "Belum ada hasil export pada sesi ini."
            )

    def _show_summary(self, summary) -> None:
        labels = {"GLOBAL": "Global Settings", "ATTENDANCE": "Attendance", "OUTLOOK_REVISI": "Outlook Revisi", "HRIS": "HRIS", "UTILITIES": "Utilities"}
        states = {"READY": "Siap", "ATTENTION": "Perlu Perhatian", "ERROR": "Error", "NOT_FOUND": "Tidak Ditemukan"}
        module_states = dict(summary.modules)
        self.import_result.show_lines(["Hasil Pemeriksaan", *(f"{labels[module]}: {states[module_states[module].value]}" if module in module_states else f"{labels[module]}: Tidak Ditemukan" for module in self.MODULES), f"Diperbarui: {summary.update_count}", f"Ditambahkan: {summary.insert_count}", f"Dihapus: {summary.delete_count}", f"Peringatan: {summary.warning_count}", f"Error: {summary.error_count}", "Perlu Persetujuan: " + ("Ya" if summary.confirmation_required else "Tidak")])

    def _toggle_advanced(self) -> None:
        if self.advanced_var.get():
            self.advanced_frame.grid(row=9, column=0, sticky="ew", pady=(6, 0))
        else:
            self.advanced_frame.grid_remove()

    def _toggle_module_choices(self) -> None:
        if self.selected_only_var.get():
            self.module_frame.grid()
        else:
            self.module_frame.grid_remove()
        self._update_apply_state()

    def select_advanced_module(self, module: str) -> None:
        if module not in self.module_vars:
            return
        self.advanced_var.set(True)
        self.selected_only_var.set(True)
        self._toggle_advanced()
        self._toggle_module_choices()
        for variable in self.module_vars.values():
            variable.set(False)
        self.module_vars[module].set(True)

    def _selected_modules(self) -> tuple[str, ...]:
        if not self.selected_only_var.get():
            return tuple(self.preview.modules) if self.preview else ()
        return tuple(module for module, variable in self.module_vars.items() if variable.get() and self.preview and module in self.preview.modules)

    def _update_apply_state(self) -> None:
        ready = bool(self.preview and self.preview.can_commit)
        if ready and self.selected_only_var.get():
            ready = bool(self._selected_modules())
        if ready and self.preview.confirmation_required:
            ready = self.risk_confirmed.get()
        self.apply_button.configure(state="normal" if ready else "disabled")

    def _require_active_database(self, title: str):
        try:
            return self.active_database()
        except Exception as exc:
            self.services.dialog_service.warning(
                title,
                (
                    f"{exc}\n\n"
                    "Buka Settings > Storage & Database, lalu inisialisasi "
                    "atau pilih database OAS-K terlebih dahulu."
                ),
            )
            return None

    def focus_import(self) -> None:
        self.import_card.focus_set()

    def focus_export(self) -> None:
        self.export_card.focus_set()

    @staticmethod
    def _module_label(module: str) -> str:
        return {"GLOBAL": "Global Settings", "ATTENDANCE": "Attendance", "OUTLOOK_REVISI": "Outlook Revisi", "HRIS": "HRIS", "UTILITIES": "Utilities"}[module]
