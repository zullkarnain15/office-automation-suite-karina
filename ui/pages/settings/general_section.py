"""Global Settings and module global-usage editor."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.constants import (
    BORDER,
    CARD_BACKGROUND,
    CARD_BODY_FONT,
    IVORY_WHITE,
    MAIN_BACKGROUND,
    ROYAL_BLUE,
    TEXT_PRIMARY,
)
from ui.pages.settings.common import SettingsSection
from ui.services.protocols import (
    GlobalSettingsDraft,
    HRISTxtSourceDraft,
    ModuleGlobalUsage,
    OutlookOperationalSettingsDraft,
)
from ui.services.karina_mascot_preferences import KarinaMascotPreferences
from ui.widgets import DateEntry, OptionChip, ResultSummary


class GeneralSection(SettingsSection):
    def __init__(self, parent, page) -> None:
        super().__init__(parent, page)
        self.rowconfigure(0, weight=1)
        viewport = ttk.Frame(self, style="OASK.TFrame")
        viewport.grid(row=0, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(
            viewport,
            highlightthickness=0,
            background=MAIN_BACKGROUND,
        )
        scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=self._canvas.yview,
        )
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(self._canvas, style="OASK.TFrame")
        window = self._canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind(
            "<Configure>",
            lambda _event: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            ),
        )
        self._canvas.bind(
            "<Configure>",
            lambda event: self._canvas.itemconfigure(window, width=event.width),
        )
        self.content.columnconfigure(0, weight=1)
        self._loaded = GlobalSettingsDraft()
        self.output_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.payroll_period_var = tk.StringVar()
        self.hris_ho_source_var = tk.StringVar()
        self.hris_branch_source_var = tk.StringVar()
        self.usage_vars: dict[str, tuple[tk.BooleanVar, tk.BooleanVar | None]] = {}
        preferences = getattr(self.page.context.mascot_controller, "preferences", None)
        preferences = preferences or KarinaMascotPreferences()
        self.mascot_enabled_var = tk.BooleanVar(value=preferences.enabled)
        self.mascot_greeting_var = tk.BooleanVar(value=preferences.greeting_enabled)
        self.mascot_mode_var = tk.StringVar(value=preferences.animation_mode)
        ttk.Label(self.content, text="Pengaturan Umum", style="SectionHeader.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        form = ttk.Frame(self.content, style="OASK.TFrame")
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Folder Output Global").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.output_var).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        browse = ttk.Button(form, text="Browse", command=self._browse)
        browse.grid(row=0, column=2)
        self.page.register_action(browse)
        ttk.Label(form, text="Tanggal Mulai Global (MM/DD/YYYY)").grid(row=1, column=0, sticky="w", pady=6)
        self.start_entry = DateEntry(form, textvariable=self.start_var, width=14)
        self.start_entry.grid(
            row=1, column=1, sticky="w", padx=8
        )
        ttk.Label(form, text="Tanggal Selesai Global (MM/DD/YYYY)").grid(row=2, column=0, sticky="w")
        self.end_entry = DateEntry(form, textvariable=self.end_var, width=14)
        self.end_entry.grid(
            row=2, column=1, sticky="w", padx=8
        )
        buttons = ttk.Frame(self.content, style="OASK.TFrame")
        buttons.grid(row=2, column=0, sticky="w", pady=10)
        for text, command in (
            ("Muat Ulang", self.load),
            ("Simpan Pengaturan Umum", self.save),
            ("Batalkan Perubahan", self.reset_unsaved),
        ):
            button = ttk.Button(buttons, text=text, command=command)
            button.pack(side="left", padx=(0, 8))
            self.page.register_action(button)
        self.usage_frame = ttk.LabelFrame(
            self.content,
            text="Penggunaan Pengaturan Global",
            padding=10,
            style="SettingsPanel.TLabelframe",
        )
        self.usage_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.outlook_frame = ttk.LabelFrame(
            self.content,
            text="Outlook Revisi",
            padding=10,
            style="SettingsPanel.TLabelframe",
        )
        self.outlook_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.outlook_frame.columnconfigure(1, weight=1)
        ttk.Label(
            self.outlook_frame,
            text="Payroll Period (MM-YYYY)",
            style="CardBody.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(
            self.outlook_frame,
            textvariable=self.payroll_period_var,
            width=12,
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            self.outlook_frame,
            text="Resubmit Deadline",
            style="CardBody.TLabel",
        ).grid(row=1, column=0, sticky="nw", padx=(0, 12), pady=(8, 0))
        self.resubmit_deadline_text = tk.Text(
            self.outlook_frame,
            height=3,
            wrap="word",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            selectbackground=ROYAL_BLUE,
            selectforeground=IVORY_WHITE,
            font=CARD_BODY_FONT,
            relief="solid",
            borderwidth=2,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            padx=8,
            pady=6,
        )
        self.resubmit_deadline_text.grid(
            row=1,
            column=1,
            sticky="ew",
            pady=(8, 0),
        )
        outlook_buttons = ttk.Frame(
            self.outlook_frame,
            style="CardBody.TFrame",
        )
        outlook_buttons.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(10, 0),
        )
        for text, command in (
            ("Muat Outlook", self.load_outlook),
            ("Simpan Outlook", self.save_outlook),
        ):
            button = ttk.Button(outlook_buttons, text=text, command=command)
            button.pack(side="left", padx=(0, 8))
            self.page.register_action(button)
        self.result = ResultSummary(self.content)
        self.result.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self._build_hris_txt_source_settings(row=6)
        self._build_mascot_settings(row=7)

    def _build_hris_txt_source_settings(self, *, row: int) -> None:
        frame = ttk.LabelFrame(
            self.content,
            text="HRIS TXT Source",
            padding=10,
            style="SettingsPanel.TLabelframe",
        )
        frame.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        frame.columnconfigure(1, weight=1)
        for index, (label, variable, command) in enumerate(
            (
                ("HO TXT Source Folder", self.hris_ho_source_var, self._browse_hris_ho),
                (
                    "Branch TXT Source Folder",
                    self.hris_branch_source_var,
                    self._browse_hris_branch,
                ),
            )
        ):
            ttk.Label(frame, text=label).grid(
                row=index, column=0, sticky="w", padx=(0, 10), pady=3
            )
            ttk.Entry(frame, textvariable=variable).grid(
                row=index, column=1, sticky="ew", pady=3
            )
            browse = ttk.Button(frame, text="Browse", command=command)
            browse.grid(row=index, column=2, padx=(6, 0), pady=3)
            self.page.register_action(browse)
        button = ttk.Button(
            frame, text="Simpan HRIS TXT Source", command=self.save_hris_txt_sources
        )
        button.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.page.register_action(button)

    def _build_mascot_settings(self, *, row: int) -> None:
        frame = ttk.LabelFrame(
            self.content,
            text="Karina Mascot",
            padding=10,
            style="SettingsPanel.TLabelframe",
        )
        frame.grid(row=row, column=0, sticky="ew")
        ttk.Checkbutton(
            frame, text="Enable Karina Mascot", variable=self.mascot_enabled_var
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Tampilkan Karina sebagai mascot OAS-K.", style="CardBody.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Checkbutton(
            frame, text="Show Greeting", variable=self.mascot_greeting_var
        ).grid(row=2, column=0, sticky="w")
        ttk.Label(frame, text="Tampilkan sapaan Karina saat aplikasi dibuka.", style="CardBody.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 6))
        ttk.Label(frame, text="Animation Mode").grid(row=4, column=0, sticky="w")
        for column, (label, value) in enumerate((("Normal", "normal"),), start=0):
            ttk.Radiobutton(frame, text=label, value=value, variable=self.mascot_mode_var).grid(row=5, column=column, sticky="w", padx=(0, 10))
        for column, (label, value) in enumerate((("Reduced", "reduced"), ("Static", "static")), start=1):
            ttk.Radiobutton(frame, text=label, value=value, variable=self.mascot_mode_var).grid(row=5, column=column, sticky="w", padx=(0, 10))
        ttk.Label(frame, text="Atur tingkat animasi mascot.", style="CardBody.TLabel").grid(row=6, column=0, columnspan=3, sticky="w")
        button = ttk.Button(frame, text="Simpan Karina Mascot", command=self.save_mascot)
        button.grid(row=7, column=0, sticky="w", pady=(8, 0))
        self.page.register_action(button)

    def save_mascot(self) -> None:
        value = KarinaMascotPreferences.normalized(
            self.mascot_enabled_var.get(),
            self.mascot_greeting_var.get(),
            self.mascot_mode_var.get(),
        )
        try:
            saved = self.services.mascot_preferences.save(value)
        except Exception as exc:
            self.services.dialog_service.warning("Karina Mascot", str(exc))
            return
        self.mascot_enabled_var.set(saved.enabled)
        self.mascot_greeting_var.set(saved.greeting_enabled)
        self.mascot_mode_var.set(saved.animation_mode)
        controller = self.page.context.mascot_controller
        if controller is not None:
            controller.apply_preferences(saved, start=True)
        self.result.show_lines(["Pengaturan Karina Mascot tersimpan."])

    def _browse_hris_ho(self) -> None:
        self._browse_hris_source(self.hris_ho_source_var, "Pilih Folder TXT HRIS HO")

    def _browse_hris_branch(self) -> None:
        self._browse_hris_source(
            self.hris_branch_source_var, "Pilih Folder TXT HRIS Branch"
        )

    def _browse_hris_source(self, variable: tk.StringVar, title: str) -> None:
        path = self.services.dialog_service.select_folder(title=title)
        if path is not None:
            variable.set(str(path))

    def _apply_hris_txt_sources(self, value: HRISTxtSourceDraft) -> None:
        self.hris_ho_source_var.set(value.ho_folder)
        self.hris_branch_source_var.set(value.branch_folder)

    def save_hris_txt_sources(self) -> None:
        database = self._require_active_database("Simpan HRIS TXT Source")
        if database is None:
            return
        draft = HRISTxtSourceDraft(
            self.hris_ho_source_var.get(), self.hris_branch_source_var.get()
        )

        def done(value: HRISTxtSourceDraft) -> None:
            self._apply_hris_txt_sources(value)
            self.result.show_lines(["HRIS TXT Source tersimpan."])

        self.page.run_task(
            lambda: self.services.database_service.save_hris_txt_source_preferences(
                database, draft
            ),
            on_success=done,
            message="Menyimpan HRIS TXT Source...",
        )

    def _browse(self) -> None:
        value = self.services.dialog_service.select_folder(
            title="Pilih Global Output Root"
        )
        if value is not None:
            self.output_var.set(str(value))

    def load(self) -> None:
        database = self._require_active_database("Muat Ulang Global Settings")
        if database is None:
            return

        def done(value) -> None:
            draft, usages, outlook, hris_sources = value
            self._loaded = draft
            self._apply(draft)
            self._show_usage(usages)
            self._apply_outlook(outlook)
            self._apply_hris_txt_sources(hris_sources)
            self.result.show_lines(["Global Settings berhasil dibaca."])

        self.page.run_task(
            lambda: (
                self.services.database_service.load_global_settings(database),
                self.services.database_service.load_module_global_usage(database),
                self.services.database_service.load_outlook_operational_settings(
                    database
                ),
                self.services.database_service.load_hris_txt_source_preferences(
                    database
                ),
            ),
            on_success=done,
            message="Membaca Global Settings...",
        )

    def save(self) -> None:
        try:
            draft = self.current_draft()
        except ValueError as exc:
            self.services.dialog_service.warning("Format Tanggal", str(exc))
            return
        changes = [
            f"Output: {self._loaded.output_root or '-'} → {draft.output_root or '-'}",
            f"Period: {self._loaded.period_start or '-'} / "
            f"{self._loaded.period_end or '-'} → "
            f"{draft.period_start or '-'} / {draft.period_end or '-'}",
        ]
        if not self.services.dialog_service.confirm(
            "Simpan Global Settings",
            "\n".join(changes) + "\n\nFolder tidak akan dibuat otomatis.",
        ):
            return
        database = self._require_active_database("Simpan Global Settings")
        if database is None:
            return

        def done(value) -> None:
            self._loaded = value
            self._apply(value)
            self.result.show_lines(["Global Settings tersimpan dan diaudit."])

        self.page.run_task(
            lambda: self.services.database_service.save_global_settings(
                database, draft
            ),
            on_success=done,
            message="Menyimpan Global Settings...",
        )

    def save_usage(self) -> None:
        values = tuple(
            ModuleGlobalUsage(
                module,
                module,
                output.get(),
                period.get() if period is not None else None,
                True,
            )
            for module, (output, period) in self.usage_vars.items()
        )
        database = self._require_active_database("Simpan Penggunaan Modul")
        if database is None:
            return
        self.page.run_task(
            lambda: self.services.database_service.save_module_global_usage(
                database, values
            ),
            on_success=lambda result: self.result.show_lines(
                ["Penggunaan pengaturan global tersimpan."]
            ),
            message="Menyimpan penggunaan global...",
        )

    def load_outlook(self) -> None:
        database = self._require_active_database("Muat Outlook Settings")
        if database is None:
            return

        def done(value) -> None:
            self._apply_outlook(value)
            self.result.show_lines(["Outlook Settings berhasil dibaca."])

        self.page.run_task(
            lambda: self.services.database_service.load_outlook_operational_settings(
                database
            ),
            on_success=done,
            message="Membaca Outlook Settings...",
        )

    def save_outlook(self) -> None:
        draft = OutlookOperationalSettingsDraft(
            self.payroll_period_var.get().strip(),
            self.resubmit_deadline_text.get("1.0", "end-1c").strip(),
        )
        if not self.services.dialog_service.confirm(
            "Simpan Outlook Settings",
            (
                f"Payroll Period: {draft.payroll_period or '-'}\n"
                "Resubmit Deadline akan langsung diperbarui di database aktif."
            ),
        ):
            return
        database = self._require_active_database("Simpan Outlook Settings")
        if database is None:
            return

        def done(value) -> None:
            self._apply_outlook(value)
            self.result.show_lines(
                ["Outlook Settings tersimpan langsung ke database."]
            )

        self.page.run_task(
            lambda: self.services.database_service.save_outlook_operational_settings(
                database,
                draft,
            ),
            on_success=done,
            message="Menyimpan Outlook Settings...",
        )

    def reset_unsaved(self) -> None:
        self._apply(self._loaded)

    def current_draft(self) -> GlobalSettingsDraft:
        return GlobalSettingsDraft(
            self.output_var.get().strip(),
            self.start_entry.get_iso(),
            self.end_entry.get_iso(),
        )

    def _apply(self, value: GlobalSettingsDraft) -> None:
        self.output_var.set(value.output_root)
        self.start_entry.set_iso(value.period_start)
        self.end_entry.set_iso(value.period_end)

    def _apply_outlook(self, value: OutlookOperationalSettingsDraft) -> None:
        self.payroll_period_var.set(value.payroll_period)
        self.resubmit_deadline_text.delete("1.0", "end")
        self.resubmit_deadline_text.insert("1.0", value.resubmit_deadline)

    def _show_usage(self, values) -> None:
        for child in self.usage_frame.winfo_children():
            child.destroy()
        self.usage_vars.clear()
        for row, value in enumerate(values):
            ttk.Label(
                self.usage_frame,
                text=value.label,
                style="CardBody.TLabel",
            ).grid(row=row, column=0, sticky="w", padx=(0, 12))
            output = tk.BooleanVar(value=value.use_global_output)
            output_box = OptionChip(
                self.usage_frame,
                text="Gunakan Output Global",
                variable=output,
            )
            output_box.grid(row=row, column=1, sticky="w")
            period = None
            period_box = None
            if value.use_global_period is None:
                ttk.Label(
                    self.usage_frame,
                    text="Tidak digunakan oleh fitur ini",
                    style="CardBody.TLabel",
                ).grid(row=row, column=2, sticky="w")
            else:
                period = tk.BooleanVar(value=value.use_global_period)
                period_box = OptionChip(
                    self.usage_frame,
                    text="Gunakan Periode Global",
                    variable=period,
                )
                period_box.grid(row=row, column=2, sticky="w")
            if not value.available:
                for chip in (output_box, period_box):
                    if chip is not None:
                        chip.configure(cursor="", state="disabled")
                        chip.unbind("<Button-1>")
            else:
                self.usage_vars[value.module] = (output, period)
        button = ttk.Button(
            self.usage_frame,
            text="Simpan Penggunaan Modul",
            command=self.save_usage,
        )
        button.grid(row=len(values), column=0, pady=(10, 0), sticky="w")
        self.page.register_action(button)

    def _require_active_database(self, title: str):
        try:
            return self.active_database()
        except Exception as exc:
            self.services.dialog_service.warning(
                title,
                (
                    f"{exc}\n\n"
                    "Buka tab Storage & Database lalu initialize/refresh "
                    "database terlebih dahulu."
                ),
            )
            return None
