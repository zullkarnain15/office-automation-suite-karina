"""Text status indicator."""

from __future__ import annotations

from tkinter import ttk


class StatusBadge(ttk.Label):
    def __init__(self, parent, text: str = "Belum diperiksa") -> None:
        super().__init__(parent, text=text, style=_style_for_text(text))

    def set(self, text: str) -> None:
        self.configure(text=text, style=_style_for_text(text))


def _style_for_text(text: str) -> str:
    normalized = text.replace("_", " ").casefold()
    if any(value in normalized for value in ("gagal", "failed", "error", "batal")):
        return "StatusError.TLabel"
    if any(value in normalized for value in ("warning", "perhatian", "menunggu")):
        return "StatusWarning.TLabel"
    if any(value in normalized for value in ("running", "berjalan", "info")):
        return "StatusInfo.TLabel"
    if any(
        value in normalized
        for value in ("siap", "ready", "berhasil", "completed", "healthy")
    ):
        return "StatusReady.TLabel"
    return "CardStatus.TLabel"
