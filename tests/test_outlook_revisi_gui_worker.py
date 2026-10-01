from __future__ import annotations

import sys
from types import SimpleNamespace

import outlook.gui as outlook_gui
from outlook.gui import OutlookRevisiGUI


class _DeferredRoot:
    def __init__(self) -> None:
        self.callbacks = []

    def after(self, _delay: int, callback) -> None:
        self.callbacks.append(callback)


class _Variable:
    def __init__(self, value) -> None:
        self.value = value

    def get(self):
        return self.value


def test_start_requires_selected_workflow(monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        outlook_gui.messagebox,
        "showwarning",
        lambda _title, message, **_kwargs: warnings.append(message),
    )
    gui = OutlookRevisiGUI.__new__(OutlookRevisiGUI)
    gui.root = object()
    gui.workflow_var = _Variable("")

    gui._start_process()

    assert warnings == [
        "Please select HO or Branch workflow before starting the process."
    ]


def test_worker_initializes_com_and_preserves_error(monkeypatch) -> None:
    com_calls: list[str] = []
    fake_pythoncom = SimpleNamespace(
        CoInitialize=lambda: com_calls.append("initialize"),
        CoUninitialize=lambda: com_calls.append("uninitialize"),
    )
    monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)

    class FailingEngine:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self):
            raise RuntimeError("Outlook worker detail")

    monkeypatch.setattr(outlook_gui, "OutlookRevisiEngine", FailingEngine)

    gui = OutlookRevisiGUI.__new__(OutlookRevisiGUI)
    gui.root = _DeferredRoot()
    handled_errors: list[Exception] = []
    gui._handle_error = handled_errors.append

    gui._run_process_worker("config.xlsx", "HO", True, 25)

    assert com_calls == ["initialize", "uninitialize"]
    assert handled_errors == []
    gui.root.callbacks[0]()
    assert str(handled_errors[0]) == "Outlook worker detail"


def test_worker_passes_main_thread_values_to_engine(monkeypatch) -> None:
    fake_pythoncom = SimpleNamespace(
        CoInitialize=lambda: None,
        CoUninitialize=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)
    received: dict[str, object] = {}
    expected_result = object()

    class SuccessfulEngine:
        def __init__(self, **kwargs) -> None:
            received.update(kwargs)

        def run(self):
            return expected_result

    monkeypatch.setattr(outlook_gui, "OutlookRevisiEngine", SuccessfulEngine)

    gui = OutlookRevisiGUI.__new__(OutlookRevisiGUI)
    gui.root = _DeferredRoot()
    handled_results: list[object] = []
    gui._handle_result = handled_results.append

    gui._run_process_worker("chosen.xlsx", "Branch", False, 10)
    gui.root.callbacks[0]()

    assert received == {
        "configuration_file": "chosen.xlsx",
        "workflow": "Branch",
        "dry_run": False,
        "message_limit": 10,
    }
    assert handled_results == [expected_result]
