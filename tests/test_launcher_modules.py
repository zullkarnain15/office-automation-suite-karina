from unittest.mock import Mock

import main


def test_launcher_opens_all_three_module_guis(monkeypatch) -> None:
    root = object()
    windows: list[Mock] = []
    opened: list[tuple[str, Mock]] = []

    def create_window(parent):
        assert parent is root
        window = Mock()
        windows.append(window)
        return window

    monkeypatch.setattr(main.tk, "Toplevel", create_window)
    monkeypatch.setattr(
        main,
        "AttendanceGUI",
        lambda window: opened.append(("Attendance", window)),
    )
    monkeypatch.setattr(
        main,
        "HRISUploadGUI",
        lambda window: opened.append(("HRIS", window)),
    )
    monkeypatch.setattr(
        main,
        "OutlookRevisiGUI",
        lambda window: opened.append(("Outlook", window)),
    )

    main.open_attendance_module(root)
    main.open_hris_module(root)
    main.open_outlook_module(root)

    assert [name for name, _ in opened] == ["Attendance", "HRIS", "Outlook"]
    assert [window for _, window in opened] == windows
    for window in windows:
        window.transient.assert_called_once_with(root)
        window.lift.assert_called_once_with()
        window.focus_force.assert_called_once_with()
