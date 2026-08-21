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


def test_next_upload_uses_direct_url_when_sidebar_link_is_missing(
    monkeypatch,
) -> None:
    navigator = HRISNavigator(page=object())
    events: list[str] = []
    monkeypatch.setattr(
        navigator,
        "_click_overtime_upload_attendance_link",
        lambda: (_ for _ in ()).throw(RuntimeError("link missing")),
    )
    monkeypatch.setattr(
        navigator,
        "_open_overtime_upload_attendance_url",
        lambda: events.append("direct URL"),
    )
    monkeypatch.setattr(
        navigator,
        "verify_run_control_search_opened",
        lambda: True,
    )

    navigator.prepare_next_upload()

    assert events == ["direct URL"]


def test_sidebar_link_locator_ignores_identical_page_title(monkeypatch) -> None:
    page = Mock()
    page.frames = []
    link = page.locator.return_value.first
    navigator = HRISNavigator(page=page)
    monkeypatch.setattr(navigator, "_wait_after_navigation_action", lambda: None)

    navigator._click_overtime_upload_attendance_link()

    page.locator.assert_called_once_with(
        "#crefli_IDOT_UPLOAD_ATT_GBL > a"
    )
    link.wait_for.assert_called_once_with(state="visible", timeout=1_000)
    link.click.assert_called_once_with()


def test_sidebar_link_falls_back_to_component_href(monkeypatch) -> None:
    page = Mock()
    page.frames = []
    first = Mock()
    second = Mock()
    third = Mock()
    fourth = Mock()
    first.wait_for.side_effect = RuntimeError("missing primary ID")
    second.wait_for.side_effect = RuntimeError("missing alternate ID")
    third.wait_for.side_effect = RuntimeError("missing menuitem role")
    page.locator.side_effect = [
        SimpleNamespace(first=first),
        SimpleNamespace(first=second),
        SimpleNamespace(first=third),
        SimpleNamespace(first=fourth),
    ]
    navigator = HRISNavigator(page=page)
    monkeypatch.setattr(navigator, "_wait_after_navigation_action", lambda: None)

    navigator._click_overtime_upload_attendance_link()

    assert page.locator.call_args_list[-1].args == (
        "a[href*='IDOT_ATTENDANCE.IDOT_UPLOAD_ATT.GBL']",
    )
    fourth.click.assert_called_once_with()


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
