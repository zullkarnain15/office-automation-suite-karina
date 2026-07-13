from types import SimpleNamespace
from unittest.mock import Mock

from hris.batch_uploader import HRISBatchUploader
from hris.navigator import HRISNavigator
from hris.uploader import HRISUploadItemResult


def test_next_upload_clicks_overtime_upload_menu_once(monkeypatch) -> None:
    navigator = HRISNavigator(page=object())
    events: list[str] = []

    monkeypatch.setattr(
        navigator,
        "verify_run_control_search_opened",
        lambda: True,
    )
    monkeypatch.setattr(
        navigator,
        "_click_overtime_upload_attendance_link",
        lambda: events.append("Overtime Upload Attendance"),
    )

    navigator.prepare_next_upload()

    assert events == ["Overtime Upload Attendance"]


def test_next_upload_fails_when_run_control_search_does_not_open(
    monkeypatch,
) -> None:
    navigator = HRISNavigator(page=object())

    monkeypatch.setattr(
        navigator,
        "verify_run_control_search_opened",
        lambda: False,
    )
    monkeypatch.setattr(
        navigator,
        "_click_overtime_upload_attendance_link",
        lambda: None,
    )

    try:
        navigator.prepare_next_upload()
    except RuntimeError as error:
        assert "Run Control search page did not open" in str(error)
    else:
        raise AssertionError("Expected missing Run Control search to fail.")


def test_sidebar_link_locator_ignores_identical_page_title(monkeypatch) -> None:
    page = Mock()
    page.frames = []
    links = Mock()
    link = Mock()
    links.count.return_value = 1
    links.nth.return_value = link
    page.get_by_role.return_value = links
    navigator = HRISNavigator(page=page)
    monkeypatch.setattr(navigator, "_wait_after_navigation_action", lambda: None)

    navigator._click_overtime_upload_attendance_link()

    page.get_by_role.assert_called_once_with(
        "link",
        name="Overtime Upload Attendance",
        exact=True,
    )
    link.click.assert_called_once_with()


def test_two_successful_items_reach_next_item_navigation() -> None:
    items = [
        SimpleNamespace(
            txt_file_name=f"Attendance_{index}.txt",
            run_control_id=f"00{index}",
            status="PENDING",
            message="",
        )
        for index in (1, 2)
    ]
    uploader = HRISBatchUploader(page=Mock())
    processed: list[str] = []
    navigation_calls: list[str] = []

    def upload_one_file(plan_item, start_date, end_date):
        processed.append(plan_item.txt_file_name)
        return HRISUploadItemResult(
            True,
            "HRIS submission verified.",
            plan_item.txt_file_name,
            plan_item.run_control_id,
        )

    uploader.page_handler.upload_one_file = upload_one_file
    uploader.navigator.prepare_next_upload = lambda: navigation_calls.append(
        "next"
    )

    result = uploader.upload_batch(
        SimpleNamespace(plan_items=items),
        "07/01/2026",
        "07/15/2026",
    )

    assert result.success_count == 2
    assert result.failed_count == 0
    assert processed == ["Attendance_1.txt", "Attendance_2.txt"]
    assert navigation_calls == ["next"]
