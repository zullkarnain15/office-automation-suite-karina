"""Lightweight, optional IDLE-only presentation for the Karina mascot."""

from __future__ import annotations

import logging
import random
import tkinter as tk
from datetime import datetime
from pathlib import Path

from ui.constants import IVORY_WHITE, OLD_GOLD, SIDEBAR_BACKGROUND, TEXT_PRIMARY
from ui.icon_manager import IconManager


def greeting_for_hour(hour: int) -> str:
    """Return Karina's local-time greeting without external services."""
    if 5 <= hour <= 10:
        return "Selamat pagi! 👋"
    if 11 <= hour <= 14:
        return "Selamat siang! ✨"
    if 15 <= hour <= 18:
        return "Selamat sore! 👋"
    return "Hai! Masih semangat? ✨"


class KarinaMascotView(tk.Canvas):
    """Render Karina locally without participating in application workflows."""

    _IDLE_FILES = ("idle_01.png", "idle_02.png", "idle_03.png", "idle_04.png")
    _GREET_FILES = ("greet_01.png", "greet_02.png", "greet_03.png")
    _WORKING_FILES = (
        "working_01.png",
        "working_02.png",
        "working_03.png",
        "working_04.png",
    )
    _REACTION_FILES = {
        "success": ("success_01.png", "success_02.png", "success_03.png"),
        "warning": ("warning_01.png", "warning_02.png", "warning_03.png"),
        "error": ("error_01.png", "error_02.png", "error_03.png"),
    }
    _IMAGE_SIZE = 112
    _MASCOT_X = 64
    _BASE_Y = 140
    _SHADOW_Y = 153
    _FLOAT_INTERVAL_MS = 550
    _EXPRESSION_INTERVAL_MS = (3_000, 6_000)
    _EXPRESSION_DURATION_MS = (300, 800)
    _GREET_DELAY_MS = 1_000
    _GREET_FRAME_DURATION_MS = 450
    _GREET_SEQUENCE = (0, 1, 2, 1, 0)
    _WORKING_FRAME_DURATION_MS = 650
    _REACTION_FRAME_DURATION_MS = 550
    _REACTION_SEQUENCES = {
        "success": (0, 1, 2, 1, 0),
        "warning": (0, 1, 2, 1),
        "error": (0, 1, 2, 1),
    }
    _OUTCOME_PRIORITY = {None: 0, "success": 1, "warning": 2, "error": 3}

    def __init__(
        self,
        parent: tk.Misc,
        assets_path: str | Path,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            parent,
            width=128,
            height=210,
            background=SIDEBAR_BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
        )
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = False
        self._animation_mode = "normal"
        self._running = False
        self._float_job: str | None = None
        self._expression_job: str | None = None
        self._restore_job: str | None = None
        self._greet_job: str | None = None
        self._working_job: str | None = None
        self._reaction_job: str | None = None
        self._click_bubble_job: str | None = None
        self._float_offset = 0
        self._mascot_item: int | None = None
        self._frames: tuple[tk.PhotoImage, ...] = ()
        self._greet_frames: tuple[tk.PhotoImage, ...] = ()
        self._working_frames: tuple[tk.PhotoImage, ...] = ()
        self._reaction_frames: dict[str, tuple[tk.PhotoImage, ...]] = {}
        self._shadow: tk.PhotoImage | None = None
        self._shadow_item: int | None = None
        self._has_greeted = False
        self._greeting = False
        self._greet_index = 0
        self._working_index = 0
        self._working_count = 0
        self._reaction_name: str | None = None
        self._reaction_index = 0
        self._pending_outcome: str | None = None
        self._bubble_items: tuple[int, ...] = ()
        self._click_handler = None

        try:
            root = Path(assets_path) / "mascot" / "karina"
            idle_loader = IconManager(root / "idle", master=self, logger=self.logger)
            greet_loader = IconManager(
                root / "greet", master=self, logger=self.logger
            )
            working_loader = IconManager(
                root / "working", master=self, logger=self.logger
            )
            shadow_loader = IconManager(
                root / "common", master=self, logger=self.logger
            )
            frames = tuple(
                frame
                for name in self._IDLE_FILES
                if (frame := idle_loader.load(name, size=self._IMAGE_SIZE)) is not None
            )
            shadow = shadow_loader.load("shadow.png", size=self._IMAGE_SIZE)
            if len(frames) != len(self._IDLE_FILES) or shadow is None:
                self.logger.warning(
                    "Karina mascot asset unavailable; mascot disabled."
                )
                return
            self._frames = frames
            self._shadow = shadow
            self._greet_frames = tuple(
                frame
                for name in self._GREET_FILES
                if (frame := greet_loader.load(name, size=self._IMAGE_SIZE)) is not None
            )
            if len(self._greet_frames) != len(self._GREET_FILES):
                self.logger.warning(
                    "Karina greeting asset unavailable; greeting skipped."
                )
                self._greet_frames = ()
            self._working_frames = tuple(
                frame
                for name in self._WORKING_FILES
                if (frame := working_loader.load(name, size=self._IMAGE_SIZE)) is not None
            )
            if len(self._working_frames) != len(self._WORKING_FILES):
                self.logger.warning(
                    "Karina working asset unavailable; working state disabled."
                )
                self._working_frames = ()
            for name, files in self._REACTION_FILES.items():
                loader = IconManager(root / name, master=self, logger=self.logger)
                frames = tuple(
                    frame
                    for file_name in files
                    if (frame := loader.load(file_name, size=self._IMAGE_SIZE))
                    is not None
                )
                if len(frames) != len(files):
                    self.logger.warning(
                        "Karina %s reaction asset unavailable; reaction skipped.",
                        name,
                    )
                    continue
                self._reaction_frames[name] = frames
            self._shadow_item = self.create_image(
                self._MASCOT_X, self._SHADOW_Y, image=self._shadow
            )
            self._mascot_item = self.create_image(
                self._MASCOT_X,
                self._BASE_Y,
                image=self._frames[0],
            )
            self.tag_bind(self._mascot_item, "<Button-1>", self._on_mascot_click)
            self.enabled = True
        except Exception:
            self.logger.warning(
                "Karina mascot could not be loaded; mascot disabled.",
                exc_info=True,
            )

    def start(self, *, show_greeting: bool = True) -> None:
        """Start the two low-frequency IDLE timers after the welcome splash."""
        if not self.enabled or self._running:
            return
        self._running = True
        if self._animation_mode == "normal":
            self._schedule_float()
            self._schedule_expression()
        elif self._animation_mode == "reduced":
            self._schedule_expression(reduced=True)
        if show_greeting and self._animation_mode != "static":
            self._schedule_greeting()

    @property
    def active_state(self) -> str:
        """Return the one visual state currently allowed to own the sprite."""
        if self._working_count:
            return "WORKING"
        if self._reaction_name is not None:
            return self._reaction_name.upper()
        if self._greeting:
            return "GREET"
        return "IDLE"

    def stop(self) -> None:
        """Cancel every scheduled callback owned by this cosmetic widget."""
        self._running = False
        self._greeting = False
        self._hide_bubble()
        for attribute in (
            "_float_job",
            "_expression_job",
            "_restore_job",
            "_greet_job",
            "_working_job",
            "_reaction_job",
            "_click_bubble_job",
        ):
            job = getattr(self, attribute)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)
        self._working_count = 0
        self._reaction_name = None
        self._pending_outcome = None
        if self.enabled and self._mascot_item is not None:
            try:
                self.itemconfigure(self._mascot_item, image=self._frames[0])
                self.coords(self._mascot_item, self._MASCOT_X, self._BASE_Y)
            except tk.TclError:
                pass

    def destroy(self) -> None:
        self.stop()
        super().destroy()

    def _schedule_float(self) -> None:
        self._float_job = self.after(self._FLOAT_INTERVAL_MS, self._advance_float)

    def _advance_float(self) -> None:
        self._float_job = None
        if (
            not self._running
            or self._working_count
            or self._reaction_name
            or self._mascot_item is None
        ):
            return
        self._float_offset = 2 if self._float_offset <= 0 else -2
        try:
            self.coords(
                self._mascot_item,
                self._MASCOT_X,
                self._BASE_Y + self._float_offset,
            )
        except tk.TclError:
            return
        self._schedule_float()

    def _schedule_expression(self, *, reduced: bool = False) -> None:
        delay = random.randint(12_000, 18_000) if reduced else random.randint(*self._EXPRESSION_INTERVAL_MS)
        self._expression_job = self.after(delay, self._show_expression)

    def _show_expression(self) -> None:
        self._expression_job = None
        if (
            not self._running
            or self._working_count
            or self._reaction_name
            or self._greeting
            or self._mascot_item is None
        ):
            return
        try:
            self.itemconfigure(self._mascot_item, image=random.choice(self._frames[1:]))
            self._restore_job = self.after(
                random.randint(*self._EXPRESSION_DURATION_MS),
                self._restore_base_idle,
            )
        except tk.TclError:
            return

    def _restore_base_idle(self) -> None:
        self._restore_job = None
        if (
            not self._running
            or self._working_count
            or self._reaction_name
            or self._greeting
            or self._mascot_item is None
        ):
            return
        try:
            self.itemconfigure(self._mascot_item, image=self._frames[0])
        except tk.TclError:
            return
        if self._animation_mode != "static":
            self._schedule_expression(reduced=self._animation_mode == "reduced")

    def _schedule_greeting(self) -> None:
        if self._has_greeted or self._working_count or not self._greet_frames:
            return
        self._greet_job = self.after(self._GREET_DELAY_MS, self._start_greeting)

    def _start_greeting(self) -> None:
        self._greet_job = None
        if (
            not self._running
            or self._working_count
            or self._has_greeted
            or self._mascot_item is None
        ):
            return
        self._has_greeted = True
        self._hide_click_bubble()
        self._greeting = True
        self._cancel_idle_expression()
        self._show_bubble(greeting_for_hour(datetime.now().hour))
        self._greet_index = 0
        self._advance_greeting()

    def _advance_greeting(self) -> None:
        self._greet_job = None
        if not self._running or not self._greeting or self._mascot_item is None:
            return
        if self._greet_index >= len(self._GREET_SEQUENCE):
            self._finish_greeting()
            return
        frame_index = self._GREET_SEQUENCE[self._greet_index]
        try:
            self.itemconfigure(self._mascot_item, image=self._greet_frames[frame_index])
        except tk.TclError:
            return
        self._greet_index += 1
        self._greet_job = self.after(
            self._GREET_FRAME_DURATION_MS,
            self._advance_greeting,
        )

    def _finish_greeting(self) -> None:
        self._greeting = False
        self._hide_bubble()
        if not self._running or self._mascot_item is None:
            return
        try:
            self.itemconfigure(self._mascot_item, image=self._frames[0])
        except tk.TclError:
            return
        if self._animation_mode != "static":
            self._schedule_expression(reduced=self._animation_mode == "reduced")

    def _cancel_idle_expression(self) -> None:
        for attribute in ("_expression_job", "_restore_job"):
            job = getattr(self, attribute)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)

    def _show_bubble(self, message: str) -> None:
        self._hide_bubble()
        try:
            bubble = self.create_rectangle(
                4,
                4,
                124,
                46,
                fill=IVORY_WHITE,
                outline=OLD_GOLD,
                width=2,
            )
            tail = self.create_polygon(
                52,
                46,
                62,
                57,
                70,
                46,
                fill=IVORY_WHITE,
                outline=OLD_GOLD,
                width=2,
            )
            text = self.create_text(
                64,
                25,
                text=message,
                fill=TEXT_PRIMARY,
                font=("Segoe UI", 8, "bold"),
                width=112,
                justify="center",
            )
            self._bubble_items = (bubble, tail, text)
        except tk.TclError:
            self._bubble_items = ()

    def _hide_bubble(self) -> None:
        if not self._bubble_items:
            return
        try:
            for item in self._bubble_items:
                self.delete(item)
        except tk.TclError:
            pass
        self._bubble_items = ()

    def begin_working(self) -> None:
        """Enter WORKING after an existing UI workflow has actually started."""
        if not self.enabled or not self._running:
            return
        self._working_count += 1
        if self._working_count > 1:
            return
        self._has_greeted = True
        self._hide_click_bubble()
        self._greeting = False
        self._hide_bubble()
        self._cancel_idle_expression()
        self._cancel_job("_greet_job")
        self._cancel_job("_float_job")
        self._reaction_name = None
        self._cancel_job("_reaction_job")
        self._pending_outcome = None
        if self._shadow_item is not None and self._working_frames:
            self.itemconfigure(self._shadow_item, state="hidden")
        self._float_offset = 0
        self._working_index = 0
        if self._working_frames:
            self._advance_working()
        elif self._mascot_item is not None:
            self.itemconfigure(self._mascot_item, image=self._frames[0])

    def finish_working(self, outcome: str | None = None) -> None:
        """Leave WORKING when a UI workflow reaches any terminal outcome."""
        if self._working_count == 0:
            return
        self._remember_outcome(outcome)
        self._working_count -= 1
        if self._working_count or not self._running:
            return
        self._cancel_job("_working_job")
        outcome = self._pending_outcome
        self._pending_outcome = None
        if outcome in self._reaction_frames:
            self._start_reaction(outcome)
            return
        self._resume_idle()

    def _advance_working(self) -> None:
        self._working_job = None
        if not self._running or not self._working_count or self._mascot_item is None:
            return
        try:
            self.itemconfigure(
                self._mascot_item,
                image=self._working_frames[self._working_index],
            )
        except tk.TclError:
            return
        self._working_index = (self._working_index + 1) % len(self._working_frames)
        if self._animation_mode == "static":
            return
        self._working_job = self.after(
            self._WORKING_FRAME_DURATION_MS,
            self._advance_working,
        )

    def _cancel_job(self, attribute: str) -> None:
        job = getattr(self, attribute)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

    def _remember_outcome(self, outcome: str | None) -> None:
        if outcome not in self._OUTCOME_PRIORITY:
            return
        if self._OUTCOME_PRIORITY[outcome] >= self._OUTCOME_PRIORITY[self._pending_outcome]:
            self._pending_outcome = outcome

    def _start_reaction(self, name: str) -> None:
        self._reaction_name = name
        self._reaction_index = 0
        self._cancel_idle_expression()
        self._cancel_job("_float_job")
        if self._shadow_item is not None:
            try:
                self.itemconfigure(self._shadow_item, state="normal")
            except tk.TclError:
                return
        self._advance_reaction()

    def _advance_reaction(self) -> None:
        self._reaction_job = None
        if not self._running or self._reaction_name is None or self._mascot_item is None:
            return
        sequence = self._REACTION_SEQUENCES[self._reaction_name]
        if self._reaction_index >= len(sequence):
            self._reaction_name = None
            self._resume_idle()
            return
        frames = self._reaction_frames[self._reaction_name]
        try:
            self.itemconfigure(
                self._mascot_item,
                image=frames[sequence[self._reaction_index]],
            )
        except tk.TclError:
            return
        self._reaction_index += 1
        if self._animation_mode == "static":
            self._reaction_job = self.after(1_200, self._finish_static_reaction)
            return
        self._reaction_job = self.after(
            self._REACTION_FRAME_DURATION_MS,
            self._advance_reaction,
        )

    def _resume_idle(self) -> None:
        if not self._running or self._working_count:
            return
        if self._shadow_item is not None:
            try:
                self.itemconfigure(self._shadow_item, state="normal")
            except tk.TclError:
                return
        if self._mascot_item is None:
            return
        try:
            self.itemconfigure(self._mascot_item, image=self._frames[0])
            self.coords(self._mascot_item, self._MASCOT_X, self._BASE_Y)
        except tk.TclError:
            return
        if self._animation_mode == "normal":
            self._schedule_float()
        if self._animation_mode != "static":
            self._schedule_expression(reduced=self._animation_mode == "reduced")

    def _finish_static_reaction(self) -> None:
        self._reaction_job = None
        self._reaction_name = None
        self._resume_idle()

    def set_animation_mode(self, mode: str) -> None:
        """Apply an idle-animation preference without affecting any workflow."""
        self._animation_mode = mode if mode in {"normal", "reduced", "static"} else "normal"
        if not self._running or self.active_state != "IDLE":
            return

        self._cancel_job("_float_job")
        self._cancel_idle_expression()
        if self._animation_mode == "normal":
            self._schedule_float()
            self._schedule_expression()
        elif self._animation_mode == "reduced":
            self._schedule_expression(reduced=True)

    def set_click_handler(self, handler) -> None:
        """Register the controller-owned handler for the sprite hit target."""
        self._click_handler = handler

    def show_idle_click_bubble(self) -> bool:
        """Show the one permitted click response while the mascot is idle."""
        if not self.enabled or self.active_state != "IDLE":
            return False
        self._cancel_job("_click_bubble_job")
        self._show_bubble("Halo... ada apa yaa? 👀")
        self._click_bubble_job = self.after(2_500, self._hide_click_bubble)
        return True

    def _on_mascot_click(self, _event: object | None = None) -> None:
        if self._click_handler is None:
            return
        try:
            self._click_handler()
        except Exception:
            self.logger.warning("Karina mascot click interaction failed.", exc_info=True)

    def _hide_click_bubble(self) -> None:
        self._cancel_job("_click_bubble_job")
        self._hide_bubble()
