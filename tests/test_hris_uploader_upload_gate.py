from hris.uploader import HRISUploadPageHandler


def test_click_upload_does_not_skip_when_filename_is_populated(monkeypatch) -> None:
    handler = HRISUploadPageHandler(page=object())
    clicked = {"value": False}
    upload_button = object()

    monkeypatch.setattr(handler, "_is_any_visible", lambda selectors: False)
    monkeypatch.setattr(handler, "_find_first_visible_locator", lambda selectors, timeout=0: upload_button)
    monkeypatch.setattr(
        handler,
        "_click_upload_button",
        lambda locator: clicked.__setitem__("value", locator is upload_button),
    )

    handler._click_upload()

    assert clicked["value"]


def test_confirm_upload_ok_requires_message_or_run_button(monkeypatch) -> None:
    handler = HRISUploadPageHandler(page=object())
    ok_button = object()
    clicked = {"value": False}

    monkeypatch.setattr(handler, "_is_any_visible", lambda selectors: False)
    monkeypatch.setattr(handler, "_find_message_ok_locator", lambda timeout=0: ok_button)
    monkeypatch.setattr(
        handler,
        "_click_upload_message_ok",
        lambda locator: clicked.__setitem__("value", locator is ok_button),
    )
    monkeypatch.setattr(handler, "_try_wait_after_message_ok", lambda timeout=0: True)

    handler._confirm_upload_ok()

    assert clicked["value"]
    assert handler._upload_ok_confirmed
