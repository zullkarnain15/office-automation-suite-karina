from types import SimpleNamespace

from hris.uploader import HRISUploadPageHandler
from shared.config_manager import HRIS_POST_UPLOAD_ASSISTED_STEP_NAMES
from shared.config_manager import resolve_hris_macro_steps


def test_assisted_macro_owns_four_steps_after_choose_file() -> None:
    assert HRIS_POST_UPLOAD_ASSISTED_STEP_NAMES == (
        "upload",
        "ok_after_upload",
        "run",
        "ok_after_run",
    )


def test_legacy_four_step_macro_is_used_when_canonical_names_are_absent() -> None:
    steps = [
        SimpleNamespace(step_name=name)
        for name in (
            "run_control_id1",
            "run_control_id2",
            "run_control_id3",
            "add_attachment4",
        )
    ]

    assert resolve_hris_macro_steps(steps) == steps


def test_assisted_handoff_does_not_click_upload_with_playwright(
    monkeypatch,
    tmp_path,
) -> None:
    txt_file = tmp_path / "Attendance.txt"
    txt_file.write_text("data", encoding="utf-8")
    events: list[str] = []

    def run_macro(item, start_date, end_date):
        events.append("macro")
        return SimpleNamespace(success=True, message="Macro completed.")

    handler = HRISUploadPageHandler(
        page=object(),
        post_upload_recorder_callback=run_macro,
    )
    monkeypatch.setattr(
        handler,
        "_fill_run_control_id",
        lambda value: events.append("run_control"),
    )
    monkeypatch.setattr(
        handler,
        "_fill_date_range",
        lambda start_date, end_date: events.append("dates"),
    )
    monkeypatch.setattr(
        handler,
        "_attach_txt_file",
        lambda path: events.append("choose_file"),
    )
    monkeypatch.setattr(
        handler,
        "_wait_for_upload_macro_ready",
        lambda timeout=0: events.append("macro_ready"),
    )
    monkeypatch.setattr(
        handler,
        "_click_upload",
        lambda: events.append("playwright_upload"),
    )
    result = handler.upload_one_file(
        SimpleNamespace(
            txt_file_name=txt_file.name,
            txt_file_path=txt_file,
            run_control_id="001",
        ),
        "07/01/2026",
        "07/05/2026",
    )

    assert result.success
    assert result.message == "Macro completed."
    assert handler._real_process_submitted
    assert events == [
        "run_control",
        "dates",
        "choose_file",
        "macro_ready",
        "macro",
    ]


def test_click_upload_does_not_skip_when_filename_is_populated(monkeypatch) -> None:
    handler = HRISUploadPageHandler(page=object())
    clicked = {"value": False}
    upload_button = object()
    checked_selectors: list[str] = []

    def is_any_visible(selectors: list[str]) -> bool:
        checked_selectors.extend(selectors)
        return any("RUN" in selector.upper() for selector in selectors)

    monkeypatch.setattr(handler, "_is_any_visible", is_any_visible)
    monkeypatch.setattr(handler, "_find_first_visible_locator", lambda selectors, timeout=0: upload_button)
    monkeypatch.setattr(
        handler,
        "_click_upload_button",
        lambda locator: clicked.__setitem__("value", locator is upload_button),
    )

    handler._click_upload()

    assert clicked["value"]
    assert not any("RUN" in selector.upper() for selector in checked_selectors)


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
