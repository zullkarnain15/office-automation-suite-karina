"""Application-facing lifecycle controller for the Karina mascot."""

from __future__ import annotations

from ui.widgets.karina_mascot import KarinaMascotView


class KarinaMascotController:
    """Expose semantic mascot commands while keeping UI modules asset-agnostic."""

    def __init__(self, view: KarinaMascotView) -> None:
        self.view = view
        self.preferences = None
        self.view.set_click_handler(self.handle_click)

    @property
    def state(self) -> str:
        return self.view.active_state

    def start(self) -> None:
        self.view.start(show_greeting=bool(self.preferences is None or self.preferences.greeting_enabled))

    def process_started(self) -> None:
        self.view.begin_working()

    def process_finished(self, outcome: str | None) -> None:
        self.view.finish_working(outcome)

    def stop(self) -> None:
        self.view.stop()

    def apply_preferences(self, preferences, *, start: bool = False) -> None:
        self.preferences = preferences
        self.view.set_animation_mode(preferences.animation_mode)
        if not preferences.enabled:
            self.view.stop()
            self.view.grid_remove()
            return
        self.view.grid()
        if start and not self.view._running:
            self.view.start(show_greeting=False)

    def handle_click(self) -> bool:
        """Handle only the small, IDLE-only mascot response."""
        if self.state != "IDLE":
            return False
        return self.view.show_idle_click_bubble()
