from __future__ import annotations

from unittest.mock import Mock

from hris.uploader import ADD_ATTACHMENT_CLICK_SCRIPT
from hris.uploader import HRISUploadPageHandler


def test_add_attachment_script_targets_exact_input_not_wrappers() -> None:
    assert "input#IDOT_UPLOAD_ATT_ATTACHADD" in ADD_ATTACHMENT_CLICK_SCRIPT
    assert '"IDOT_UPLOAD_ATT_ATTACHADD"' in ADD_ATTACHMENT_CLICK_SCRIPT
    assert "'input, button, a, span, div'" not in ADD_ATTACHMENT_CLICK_SCRIPT


def test_add_attachment_uses_dom_refind_before_locator_click(monkeypatch) -> None:
    handler = HRISUploadPageHandler(page=Mock())
    stale_locator = Mock()
    attachment_frame = Mock()
    call_order: list[str] = []

    def click_script(timeout_seconds=10):
        call_order.append("exact_dom")
        return True

    monkeypatch.setattr(handler, "_click_add_attachment_with_script", click_script)
    monkeypatch.setattr(
        handler,
        "_try_find_frame_with_selector",
        lambda *args, **kwargs: attachment_frame,
    )
    monkeypatch.setattr(
        handler,
        "_find_attachment_file_input_on_page",
        lambda *args, **kwargs: None,
    )

    handler._click_add_attachment_button(stale_locator)

    assert call_order == ["exact_dom"]
    stale_locator.click.assert_not_called()
