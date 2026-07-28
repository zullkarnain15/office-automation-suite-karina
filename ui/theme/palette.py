"""Central SNES-inspired UI8 palette."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetroPalette:
    outline: str = "#222034"
    royal_blue: str = "#4D72B8"
    sky_blue: str = "#3A86C8"
    sky_blue_soft: str = "#E3F2FF"
    sky_blue_border: str = "#4D72B8"
    forest_green: str = "#5E9C3A"
    old_gold: str = "#D2A15A"
    ivory_white: str = "#F7F1DD"
    soft_background: str = "#EAE7DA"
    danger_red: str = "#B83A3A"
    text_secondary: str = "#3B394A"
    disabled_background: str = "#D7D1C0"
    disabled_text: str = "#77716A"
    log_background: str = "#222034"
    log_text: str = "#F7F1DD"


palette = RetroPalette()
