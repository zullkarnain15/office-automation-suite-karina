"""Small themed completion popup with animated GIF support."""

from __future__ import annotations

import tkinter as tk
from math import ceil
from pathlib import Path

from ui.constants import (
    BORDER,
    BUTTON_FONT,
    CARD_BACKGROUND,
    CARD_BODY_FONT,
    CARD_TITLE_FONT,
    FOREST_GREEN,
    IVORY_WHITE,
    MAIN_HEADER,
    OLD_GOLD,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEAL_HOVER,
)


class CompletionPopup(tk.Toplevel):
    """Manual-close informational popup shown after a module completes."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        module_name: str,
        message: str,
        details: tuple[str, ...] = (),
        gif_path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._frames: list[tk.PhotoImage] = []
        self._frame_index = 0
        self._animation_job: str | None = None

        self.title(f"{module_name} Selesai")
        self.transient(parent)
        self.resizable(False, False)
        self.configure(background=BORDER)

        self._load_frames(gif_path)
        self._build_content(module_name, message, details)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Return>", lambda _event: self.close())
        self.bind("<Escape>", lambda _event: self.close())

        self.update_idletasks()
        self._center(parent)
        self.lift()
        self.focus_force()
        self._animate()

    def _build_content(
        self, module_name: str, message: str, details: tuple[str, ...]
    ) -> None:
        shell = tk.Frame(self, background=BORDER, padx=2, pady=2)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, background=MAIN_HEADER)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Module telah selesai",
            background=MAIN_HEADER,
            foreground=IVORY_WHITE,
            font=CARD_TITLE_FONT,
            padx=14,
            pady=8,
        ).pack(side="left")
        tk.Frame(header, background=OLD_GOLD, width=6).pack(side="right", fill="y")

        body = tk.Frame(shell, background=CARD_BACKGROUND, padx=18, pady=16)
        body.pack(fill="both", expand=True)

        if self._frames:
            self._image_label = tk.Label(
                body,
                image=self._frames[0],
                background=CARD_BACKGROUND,
                borderwidth=0,
            )
            self._image_label.grid(row=0, column=0, rowspan=3, padx=(0, 16), sticky="n")
        else:
            self._image_label = None

        text_column = tk.Frame(body, background=CARD_BACKGROUND)
        text_column.grid(row=0, column=1, sticky="nsew")
        body.columnconfigure(1, weight=1)

        tk.Label(
            text_column,
            text=module_name,
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=CARD_TITLE_FONT,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            text_column,
            text=message,
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=CARD_BODY_FONT,
            anchor="w",
            justify="left",
            wraplength=300,
        ).pack(fill="x", pady=(6, 8))

        for detail in details:
            tk.Label(
                text_column,
                text=detail,
                background=CARD_BACKGROUND,
                foreground=TEXT_PRIMARY,
                font=CARD_BODY_FONT,
                anchor="w",
                justify="left",
                wraplength=300,
            ).pack(fill="x", pady=(0, 3))

        actions = tk.Frame(shell, background=CARD_BACKGROUND, padx=18, pady=(0, 16))
        actions.pack(fill="x")
        ok_button = tk.Button(
            actions,
            text="OK",
            command=self.close,
            background=FOREST_GREEN,
            activebackground=TEAL_HOVER,
            foreground=IVORY_WHITE,
            activeforeground=IVORY_WHITE,
            relief="solid",
            borderwidth=2,
            highlightthickness=1,
            highlightbackground=OLD_GOLD,
            font=BUTTON_FONT,
            padx=18,
            pady=6,
        )
        ok_button.pack(side="right")
        ok_button.focus_set()

    def _load_frames(self, gif_path: Path | None) -> None:
        if gif_path is None or not gif_path.exists():
            return
        index = 0
        while True:
            try:
                frame = tk.PhotoImage(file=gif_path, format=f"gif -index {index}")
            except tk.TclError:
                break
            scale = max(1, ceil(max(frame.width(), frame.height()) / 120))
            if scale > 1:
                frame = frame.subsample(scale, scale)
            self._frames.append(frame)
            index += 1

    def _animate(self) -> None:
        if len(self._frames) <= 1 or self._image_label is None:
            return
        self._frame_index = (self._frame_index + 1) % len(self._frames)
        self._image_label.configure(image=self._frames[self._frame_index])
        self._animation_job = self.after(90, self._animate)

    def _center(self, parent: tk.Misc) -> None:
        owner = parent.winfo_toplevel()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        owner.update_idletasks()
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - width) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def close(self) -> None:
        if self._animation_job is not None:
            try:
                self.after_cancel(self._animation_job)
            except tk.TclError:
                pass
            self._animation_job = None
        self.destroy()
