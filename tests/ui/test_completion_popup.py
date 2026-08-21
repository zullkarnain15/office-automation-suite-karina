from __future__ import annotations

import tkinter as tk
import time

from config.app_config import ASSETS_PATH
from ui.dialogs.completion_popup import CompletionPopup
from ui.services import dialog_service as dialog_service_module
from ui.services.dialog_service import TkDialogService


def _descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def test_completion_popup_uses_static_karina_success_and_closes_with_ok(tk_root) -> None:
    popup = CompletionPopup(
        tk_root,
        module_name="Attendance",
        message="Attendance berhasil diproses.",
        details=("Valid: 10 | Anomaly: 0",),
        gif_path=ASSETS_PATH / "mascot" / "karina" / "success" / "success_03.png",
        window_icon_path=(
            ASSETS_PATH / "mascot" / "karina" / "working" / "working_04.ico"
        ),
    )
    tk_root.update()

    assert len(popup._frames) == 1
    assert popup._window_icon_path is not None
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline:
        tk_root.update()
    assert popup.winfo_exists()

    buttons = [
        child for child in _descendants(popup) if isinstance(child, tk.Button)
    ]
    assert len(buttons) == 1
    assert buttons[0].cget("text") == "OK"

    buttons[0].invoke()
    tk_root.update_idletasks()
    assert popup not in tk_root.winfo_children()


def test_dialog_service_uses_manual_close_fallback_on_tcl_error(
    tk_root, monkeypatch
) -> None:
    shown: list[tuple[str, str]] = []

    def fail_popup(*_args, **_kwargs):
        raise tk.TclError("popup unavailable")

    monkeypatch.setattr(dialog_service_module, "CompletionPopup", fail_popup)
    monkeypatch.setattr(
        dialog_service_module.messagebox,
        "showinfo",
        lambda title, message, **_kwargs: shown.append((title, message)),
    )

    TkDialogService(tk_root).completion(
        "Attendance",
        "Attendance berhasil diproses.",
        ("Valid: 10 | Anomaly: 0",),
    )

    assert shown == [
        (
            "Attendance Selesai",
            "Attendance berhasil diproses.\n\nValid: 10 | Anomaly: 0",
        )
    ]
