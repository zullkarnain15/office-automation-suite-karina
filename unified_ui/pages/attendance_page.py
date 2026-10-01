"""Attendance placeholder page."""

from unified_ui.pages.base_page import BasePage


class AttendancePage(BasePage):
    page_title = "Attendance"
    page_description = "Attendance processing workspace."
    page_icon = "attendance"
    placeholder_text = (
        "Attendance engine integration is scheduled for the next module "
        "integration sprint."
    )
