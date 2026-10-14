from __future__ import annotations

from unittest.mock import Mock

from hris.uploader import HRISUploadPageHandler


def _field(value: str) -> Mock:
    field = Mock()
    field.input_value.return_value = value
    return field


def test_run_control_uses_exact_locator_verifies_and_presses_enter(
    monkeypatch,
) -> None:
    handler = HRISUploadPageHandler(page=Mock())
    field = _field("001")
    searches: list[tuple[list[str], int]] = []

    monkeypatch.setattr(handler, "_is_upload_form_ready", Mock(side_effect=[False, False]))

    def find(selectors, timeout=10_000, fallback_handle_script=None):
        searches.append((selectors, timeout))
        return field

    monkeypatch.setattr(handler, "_find_first_visible_locator", find)
    wait_ready = Mock()
    monkeypatch.setattr(handler, "_wait_for_upload_form_ready", wait_ready)

    handler._fill_run_control_id("001")

    assert searches == [
        (["#PRCSRUNCNTL_RUN_CNTL_ID", "[name='PRCSRUNCNTL_RUN_CNTL_ID']"], 3_000)
    ]
    field.fill.assert_called_once_with("001")
    field.input_value.assert_called_once_with(timeout=5_000)
    field.press.assert_called_once_with("Enter")
    wait_ready.assert_called_once_with(timeout=8_000)


def test_run_control_keeps_search_button_fallback_after_enter(
    monkeypatch,
) -> None:
    handler = HRISUploadPageHandler(page=Mock())
    field = _field("001")
    search_button = Mock()
    located = iter([field, search_button])

    monkeypatch.setattr(handler, "_is_upload_form_ready", Mock(side_effect=[False, False]))
    monkeypatch.setattr(
        handler,
        "_find_first_visible_locator",
        lambda *args, **kwargs: next(located),
    )
    wait_ready = Mock(side_effect=[RuntimeError("not ready"), None])
    monkeypatch.setattr(handler, "_wait_for_upload_form_ready", wait_ready)
    click = Mock()
    monkeypatch.setattr(handler, "_click_visible_locator", click)

    handler._fill_run_control_id("001")

    field.press.assert_called_once_with("Enter")
    click.assert_called_once_with(search_button)
    assert wait_ready.call_count == 2
