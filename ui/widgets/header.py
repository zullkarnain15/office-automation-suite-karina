"""Page title, subtitle, and lightweight application status header."""

from __future__ import annotations

from tkinter import ttk

from ui.icon_manager import IconManager
from ui.models import HeaderMetadata


class Header(ttk.Frame):
    def __init__(self, parent, icon_manager: IconManager | None = None) -> None:
        super().__init__(
            parent,
            style="Header.TFrame",
            padding=(20, 10, 20, 0),
        )
        self._title_icons = self._load_title_icons(icon_manager)
        self._title_animations = self._load_title_animations(icon_manager)
        self._animation_job = None
        self._animation_frames = ()
        self._animation_index = 0
        self._subtitle_job = None
        self._subtitle_text = ""
        self._subtitle_offset = 0
        self.columnconfigure(1, weight=1)
        self.actions = ttk.Frame(self, style="Header.TFrame")
        self.actions.grid(row=0, column=2, rowspan=2, padx=(14, 16))
        self.title_icon_label = ttk.Label(
            self,
            style="Header.TLabel",
        )
        self.title_label = ttk.Label(
            self,
            text="",
            style="PageTitle.TLabel",
        )
        self.title_label.grid(row=0, column=1, sticky="w")
        self.subtitle_label = ttk.Label(
            self,
            text="",
            style="PageSubtitle.TLabel",
        )
        self.subtitle_label.grid(row=1, column=1, sticky="w", pady=(3, 0))
        self.status_label = ttk.Label(
            self,
            text="- STATUS APLIKASI: Siap -",
            style="HeaderStatus.TLabel",
        )
        self.status_label.grid(row=0, column=3, rowspan=2, sticky="e")
        ttk.Frame(self, style="RPGAccent.TFrame", height=2).grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(10, 0),
        )

    def update_metadata(self, metadata: HeaderMetadata) -> None:
        self.title_label.configure(text=metadata.title)
        title_key = metadata.title.casefold()
        self._start_subtitle_marquee(metadata.subtitle)
        animation = self._title_animations.get(title_key, ())
        icon = self._title_icons.get(title_key)
        if animation:
            self._start_animation(animation)
            self._show_title_icon()
        elif icon is not None:
            self._stop_animation()
            self.title_icon_label.configure(image=icon)
            self._show_title_icon()
        else:
            self._stop_animation()
            self.title_icon_label.grid_remove()
        self.status_label.configure(
            text=f"- STATUS APLIKASI: {metadata.application_status} -"
        )

    def _show_title_icon(self) -> None:
        self.title_icon_label.grid(
            row=0,
            column=0,
            rowspan=2,
            sticky="w",
            padx=(0, 12),
        )

    def _start_animation(self, frames: tuple[object, ...]) -> None:
        if self._animation_frames == frames and self._animation_job is not None:
            return
        self._stop_animation()
        self._animation_frames = frames
        self._animation_index = 0
        self.title_icon_label.configure(image=frames[0])
        if len(frames) > 1:
            self._animation_job = self.after(40, self._advance_animation)

    def _advance_animation(self) -> None:
        self._animation_job = None
        if not self._animation_frames:
            return
        self._animation_index = (self._animation_index + 1) % len(
            self._animation_frames
        )
        self.title_icon_label.configure(
            image=self._animation_frames[self._animation_index]
        )
        self._animation_job = self.after(40, self._advance_animation)

    def _stop_animation(self) -> None:
        if self._animation_job is not None:
            try:
                self.after_cancel(self._animation_job)
            except Exception:
                pass
            self._animation_job = None
        self._animation_frames = ()
        self._animation_index = 0

    def destroy(self) -> None:
        self._stop_animation()
        self._stop_subtitle_marquee()
        super().destroy()

    def _start_subtitle_marquee(self, text: str) -> None:
        if self._subtitle_text != text:
            self._subtitle_offset = 0
        self._subtitle_text = text
        self._apply_subtitle_marquee()
        if self._subtitle_job is None:
            self._subtitle_job = self.after(160, self._advance_subtitle_marquee)

    def _advance_subtitle_marquee(self) -> None:
        self._subtitle_job = None
        if not self._subtitle_text:
            return
        loop_width = len(self._subtitle_text) + 8
        self._subtitle_offset = (self._subtitle_offset + 1) % loop_width
        self._apply_subtitle_marquee()
        self._subtitle_job = self.after(160, self._advance_subtitle_marquee)

    def _apply_subtitle_marquee(self) -> None:
        if not self._subtitle_text:
            self.subtitle_label.configure(text="")
            return
        padding = " " * 8
        marquee = f"{padding}{self._subtitle_text}"
        offset = self._subtitle_offset % len(marquee)
        self.subtitle_label.configure(text=f"{marquee[-offset:]}{marquee[:-offset]}")

    def _stop_subtitle_marquee(self) -> None:
        if self._subtitle_job is not None:
            try:
                self.after_cancel(self._subtitle_job)
            except Exception:
                pass
            self._subtitle_job = None
        self._subtitle_text = ""
        self._subtitle_offset = 0

    @staticmethod
    def _load_title_icons(
        icon_manager: IconManager | None,
    ) -> dict[str, object]:
        if icon_manager is None:
            return {}
        icon_names = {
            "dashboard": "mob_icon.png",
            "attendance": "jamur.png",
            "outlook revisi": "blue_slime.png",
            "hris": "green_slime.png",
            "utilities": "red_apple.png",
            "history": "history_wizard.png",
            "settings": "setting_stick.png",
            "system health": "sys_healt.png",
        }
        return {
            title: icon
            for title, icon_name in icon_names.items()
            if (icon := icon_manager.load(icon_name, size=32)) is not None
        }

    @staticmethod
    def _load_title_animations(
        icon_manager: IconManager | None,
    ) -> dict[str, tuple[object, ...]]:
        if icon_manager is None:
            return {}
        icon_names = {
            "dashboard": "mob_icon2.gif",
            "attendance": "jamur2.gif",
            "outlook revisi": "blue_slime2.gif",
            "hris": "green_slime2.gif",
            "utilities": "red_apple2.gif",
        }
        return {
            title: frames
            for title, icon_name in icon_names.items()
            if (frames := icon_manager.load_animation(icon_name, size=32))
        }
