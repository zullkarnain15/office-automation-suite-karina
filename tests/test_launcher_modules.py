from unittest.mock import Mock
from types import ModuleType
import sys

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


def test_launcher_lazy_imports_and_opens_reconciliation(monkeypatch) -> None:
    root = object()
    window = Mock()
    opened = []
    fake_gui = ModuleType("utilities.attendance_reconciliation.gui")
    fake_gui.AttendanceReconciliationGUI = lambda target: opened.append(target)
    monkeypatch.setitem(
        sys.modules, "utilities.attendance_reconciliation.gui", fake_gui
    )
    monkeypatch.setattr(main.tk, "Toplevel", lambda parent: window)

    main.open_utilities_module(root)

    assert opened == [window]
    window.transient.assert_called_once_with(root)
    window.lift.assert_called_once_with()
    window.focus_force.assert_called_once_with()
