from __future__ import annotations

import logging
from types import SimpleNamespace
from tkinter import ttk

from ui.context import AppContext
from ui.pages.finger_monitoring_page import FingerMonitoringPage
from ui.theme.finger_monitoring import finger_palette


def test_status_kpi_cards_use_distinct_semantic_colors(tk_root, tmp_path) -> None:
    context = AppContext(
        project_root=tmp_path,
        assets_path=tmp_path / "assets",
        application_version="test",
        logger=logging.getLogger("finger-monitoring-kpi-colors"),
        app_services=SimpleNamespace(
            finger_monitoring_service=SimpleNamespace(),
        ),
    )
    page = FingerMonitoringPage(tk_root, context)
    style = ttk.Style(tk_root)
    expected = {
        "Total": ("Total", finger_palette.royal_blue),
        "Online": ("Online", finger_palette.pipe_green),
        "Offline": ("Offline", finger_palette.orange),
        "Alert ≥3 Days": ("Alert", finger_palette.danger),
    }

    assert set(page.kpi_cards) == set(expected)
    for title, (style_suffix, color) in expected.items():
        card = page.kpi_cards[title]
        frame_style = f"FingerMonitoring{style_suffix}Card.TFrame"
        label_style = f"FingerMonitoring{style_suffix}Card.TLabel"
        assert card.cget("style") == frame_style
        assert style.lookup(frame_style, "background") == color
        assert all(child.cget("style") == label_style for child in card.winfo_children())
        assert style.lookup(label_style, "foreground") == finger_palette.white
    page.destroy()
