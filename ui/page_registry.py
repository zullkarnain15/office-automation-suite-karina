"""Ordered page registry with lazy import factories."""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Iterator
from typing import Any

from ui.models import PageDefinition


class PageRegistry:
    def __init__(
        self,
        definitions: Iterable[PageDefinition] = (),
    ) -> None:
        self._definitions: dict[str, PageDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: PageDefinition) -> None:
        if definition.page_id in self._definitions:
            raise ValueError(f"Duplicate page ID is not allowed: {definition.page_id}")
        self._definitions[definition.page_id] = definition

    def get(self, page_id: str) -> PageDefinition:
        try:
            return self._definitions[page_id]
        except KeyError as exc:
            raise KeyError(f"Unknown page ID: {page_id}") from exc

    def __iter__(self) -> Iterator[PageDefinition]:
        return iter(self._definitions.values())

    def __len__(self) -> int:
        return len(self._definitions)

    @property
    def page_ids(self) -> tuple[str, ...]:
        return tuple(self._definitions)


def lazy_page_factory(module_name: str, class_name: str):
    def factory(parent: Any, context: Any) -> Any:
        module = importlib.import_module(module_name)
        page_class = getattr(module, class_name)
        return page_class(parent, context)

    return factory


def build_default_page_registry() -> PageRegistry:
    metadata = (
        (
            "dashboard",
            "Dashboard",
            "Ringkasan aktivitas dan status Office Automation Suite – Karina",
            "dashboard.ico",
            "dashboard_page",
            "DashboardPage",
        ),
        (
            "attendance",
            "Attendance",
            "Ekstraksi dan validasi data mesin absensi",
            "attendance.ico",
            "attendance_page",
            "AttendancePage",
        ),
        (
            "outlook_revisi",
            "Outlook Revisi",
            "Pengelolaan email, attachment, dan validasi Outlook",
            "outlook_revisi.ico",
            "outlook_revisi_page",
            "OutlookRevisiPage",
        ),
        (
            "hris",
            "HRIS",
            "Persiapan dan bantuan proses unggah data HRIS",
            "hris.ico",
            "hris_page",
            "HRISPage",
        ),
        (
            "utilities",
            "Utilities",
            "Alat bantu perbandingan dan konsolidasi data",
            "utilities.ico",
            "utilities_page",
            "UtilitiesPage",
        ),
        (
            "history",
            "History",
            "Riwayat pekerjaan dan hasil proses aplikasi",
            "history.ico",
            "history_page",
            "HistoryPage",
        ),
        (
            "settings",
            "Settings",
            "Konfigurasi aplikasi, penyimpanan, dan pemulihan",
            "settings.ico",
            "settings_page",
            "SettingsPage",
        ),
        (
            "system_health",
            "System Health",
            "Status kesiapan komponen Office Automation Suite – Karina",
            "system_health.ico",
            "system_health_page",
            "SystemHealthPage",
        ),
    )
    return PageRegistry(
        PageDefinition(
            page_id=page_id,
            title=title,
            subtitle=subtitle,
            icon_name=icon_name,
            factory=lazy_page_factory(
                f"ui.pages.{module_name}",
                class_name,
            ),
        )
        for (
            page_id,
            title,
            subtitle,
            icon_name,
            module_name,
            class_name,
        ) in metadata
    )
