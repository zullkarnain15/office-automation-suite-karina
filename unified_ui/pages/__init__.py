"""Lazy page registry for the Unified UI shell."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class PageSpec:
    """Navigation metadata for a lazily imported page."""

    key: str
    title: str
    icon_name: str
    module_name: str
    class_name: str


PAGE_REGISTRY: tuple[PageSpec, ...] = (
    PageSpec(
        "dashboard",
        "Dashboard",
        "dashboard",
        "unified_ui.pages.dashboard_page",
        "DashboardPage",
    ),
    PageSpec(
        "attendance",
        "Attendance",
        "attendance",
        "unified_ui.pages.attendance_page",
        "AttendancePage",
    ),
    PageSpec(
        "outlook_revisi",
        "Outlook Revisi",
        "outlook_revisi",
        "unified_ui.pages.outlook_revisi_page",
        "OutlookRevisiPage",
    ),
    PageSpec(
        "hris",
        "HRIS",
        "hris",
        "unified_ui.pages.hris_page",
        "HRISPage",
    ),
    PageSpec(
        "utilities",
        "Utilities",
        "utilities",
        "unified_ui.pages.utilities_page",
        "UtilitiesPage",
    ),
    PageSpec(
        "history",
        "History",
        "history",
        "unified_ui.pages.history_page",
        "HistoryPage",
    ),
    PageSpec(
        "settings",
        "Settings",
        "settings",
        "unified_ui.pages.settings_page",
        "SettingsPage",
    ),
    PageSpec(
        "system_health",
        "System Health",
        "system_health",
        "unified_ui.pages.system_health_page",
        "SystemHealthPage",
    ),
)

PAGE_BY_KEY = MappingProxyType({page.key: page for page in PAGE_REGISTRY})

if len(PAGE_BY_KEY) != len(PAGE_REGISTRY):
    raise ValueError("Unified UI navigation keys must be unique.")

__all__ = ["PAGE_BY_KEY", "PAGE_REGISTRY", "PageSpec"]
