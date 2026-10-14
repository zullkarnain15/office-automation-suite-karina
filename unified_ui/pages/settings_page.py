"""Settings placeholder page."""

from unified_ui.pages.base_page import BasePage


class SettingsPage(BasePage):
    page_title = "Settings"
    page_description = "Central application preferences."
    page_icon = "settings"
    placeholder_text = (
        "Central configuration will be available after SQLite integration."
    )
