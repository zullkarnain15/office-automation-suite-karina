"""HRIS placeholder page."""

from unified_ui.pages.base_page import BasePage


class HRISPage(BasePage):
    page_title = "HRIS"
    page_description = "Assisted upload workspace."
    page_icon = "hris"
    placeholder_text = (
        "HRIS assisted upload integration is not active in this sprint."
    )
