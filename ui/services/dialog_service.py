"""Central file-dialog and confirmation wrapper."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from config.app_config import ASSETS_PATH
from ui.dialogs.completion_popup import CompletionPopup


class TkDialogService:
    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent

    def select_folder(self, *, title: str) -> Path | None:
        value = filedialog.askdirectory(parent=self.parent, title=title)
        return Path(value) if value else None

    def select_file(
        self,
        *,
        title: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> Path | None:
        value = filedialog.askopenfilename(
            parent=self.parent,
            title=title,
            filetypes=filetypes,
        )
        return Path(value) if value else None

    def select_files(
        self,
        *,
        title: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> tuple[Path, ...]:
        values = filedialog.askopenfilenames(
            parent=self.parent,
            title=title,
            filetypes=filetypes,
        )
        return tuple(Path(value) for value in values)

    def save_file(
        self,
        *,
        title: str,
        default_name: str,
        filetypes: Sequence[tuple[str, str]],
    ) -> Path | None:
        value = filedialog.asksaveasfilename(
            parent=self.parent,
            title=title,
            initialfile=default_name,
            filetypes=filetypes,
        )
        return Path(value) if value else None

    def confirm(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self.parent))

    def typed_confirm(self, title: str, message: str, expected: str) -> bool:
        value = simpledialog.askstring(title, message, parent=self.parent)
        return value == expected

    def prompt_text(self, title: str, message: str) -> str | None:
        return simpledialog.askstring(title, message, parent=self.parent)

    def info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self.parent)

    def completion(
        self, module_name: str, message: str, details: tuple[str, ...] = ()
    ) -> None:
        try:
            CompletionPopup(
                self.parent,
                module_name=module_name,
                message=message,
                details=details,
                gif_path=(
                    ASSETS_PATH
                    / "mascot"
                    / "karina"
                    / "success"
                    / "success_03.png"
                ),
                window_icon_path=(
                    ASSETS_PATH
                    / "mascot"
                    / "karina"
                    / "working"
                    / "working_04.ico"
                ),
            )
        except (OSError, tk.TclError):
            detail_text = "\n".join(details)
            fallback_message = message
            if detail_text:
                fallback_message = f"{message}\n\n{detail_text}"
            messagebox.showinfo(
                f"{module_name} Selesai",
                fallback_message,
                parent=self.parent,
            )

    def warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message, parent=self.parent)

    def error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self.parent)
