"""Coverage for the optional, presentation-only Karina IDLE widget."""

from __future__ import annotations

from shutil import copy2

from config.app_config import PROJECT_ROOT
from ui.mascot_outcome import classify_mascot_outcome
from ui.widgets.karina_mascot_controller import KarinaMascotController
from ui.widgets.karina_mascot import KarinaMascotView, greeting_for_hour


def test_karina_assets_are_complete_pixel_art_pngs() -> None:
    root = PROJECT_ROOT / "assets" / "mascot" / "karina"
    assert (root / "common" / "shadow.png").is_file()
    assert all((root / "idle" / f"idle_0{index}.png").is_file() for index in range(1, 5))
    assert all((root / "greet" / f"greet_0{index}.png").is_file() for index in range(1, 4))
    for state in ("success", "warning", "error"):
        assert all(
            (root / state / f"{state}_0{index}.png").is_file()
            for index in range(1, 4)
        )


def test_karina_local_time_greeting_mapping() -> None:
    assert greeting_for_hour(5) == "Selamat pagi! 👋"
    assert greeting_for_hour(10) == "Selamat pagi! 👋"
    assert greeting_for_hour(11) == "Selamat siang! ✨"
    assert greeting_for_hour(14) == "Selamat siang! ✨"
    assert greeting_for_hour(15) == "Selamat sore! 👋"
    assert greeting_for_hour(18) == "Selamat sore! 👋"
    assert greeting_for_hour(19) == "Hai! Masih semangat? ✨"
    assert greeting_for_hour(4) == "Hai! Masih semangat? ✨"


def test_karina_runs_idle_and_cleans_its_timers(tk_root) -> None:
    mascot = KarinaMascotView(tk_root, PROJECT_ROOT / "assets")
    controller = KarinaMascotController(mascot)
    mascot.pack()

    assert mascot.enabled
    assert mascot._frames[0].width() == mascot._IMAGE_SIZE
    assert len(mascot._greet_frames) == 3
    assert len(mascot._working_frames) == 4
    assert set(mascot._reaction_frames) == {"success", "warning", "error"}
    controller.start()
    assert controller.state == "IDLE"
    assert controller.handle_click()
    first_click_job = mascot._click_bubble_job
    assert mascot._bubble_items
    assert controller.handle_click()
    assert mascot._click_bubble_job is not None
    assert mascot._click_bubble_job != first_click_job
    assert mascot._float_job is not None
    assert mascot._expression_job is not None
    assert mascot._greet_job is not None

    mascot.after_cancel(mascot._expression_job)
    mascot._expression_job = None
    mascot.after_cancel(mascot._greet_job)
    mascot._greet_job = None
    mascot._start_greeting()
    assert mascot._greeting
    assert controller.state == "GREET"
    assert not controller.handle_click()
    assert mascot._bubble_items
    assert mascot._restore_job is None
    assert mascot.itemcget(mascot._mascot_item, "image") == str(
        mascot._greet_frames[0]
    )
    for frame_index in (1, 2, 1, 0):
        mascot.after_cancel(mascot._greet_job)
        mascot._greet_job = None
        mascot._advance_greeting()
        assert mascot.itemcget(mascot._mascot_item, "image") == str(
            mascot._greet_frames[frame_index]
        )
    mascot.after_cancel(mascot._greet_job)
    mascot._greet_job = None
    mascot._advance_greeting()
    assert not mascot._greeting
    assert not mascot._bubble_items
    assert mascot._expression_job is not None
    controller.process_started()
    assert mascot._working_count == 1
    assert controller.state == "WORKING"
    assert not controller.handle_click()
    assert mascot._working_job is not None
    assert mascot._float_job is None
    assert mascot._expression_job is None
    assert mascot.itemcget(mascot._mascot_item, "image") == str(
        mascot._working_frames[0]
    )
    mascot.after_cancel(mascot._working_job)
    mascot._working_job = None
    mascot._advance_working()
    assert mascot.itemcget(mascot._mascot_item, "image") == str(
        mascot._working_frames[1]
    )
    controller.process_finished("success")
    assert mascot._working_count == 0
    assert mascot._working_job is None
    assert mascot._reaction_name == "success"
    assert controller.state == "SUCCESS"
    assert not controller.handle_click()
    assert mascot._reaction_job is not None
    assert mascot.itemcget(mascot._mascot_item, "image") == str(
        mascot._reaction_frames["success"][0]
    )
    for frame_index in (1, 2, 1, 0):
        mascot.after_cancel(mascot._reaction_job)
        mascot._reaction_job = None
        mascot._advance_reaction()
        assert mascot.itemcget(mascot._mascot_item, "image") == str(
            mascot._reaction_frames["success"][frame_index]
        )
    mascot.after_cancel(mascot._reaction_job)
    mascot._reaction_job = None
    mascot._advance_reaction()
    assert mascot._reaction_name is None
    assert mascot._float_job is not None
    assert mascot._expression_job is not None
    assert controller.handle_click()
    assert mascot._bubble_items
    controller.process_started()
    assert not mascot._bubble_items
    assert mascot._reaction_name is None
    controller.process_finished("warning")
    assert mascot._reaction_name == "warning"
    controller.stop()

    assert mascot._float_job is None
    assert mascot._expression_job is None
    assert mascot._restore_job is None
    assert mascot._greet_job is None
    assert mascot._working_job is None
    assert mascot._reaction_job is None
    assert mascot._click_bubble_job is None
    assert not mascot._bubble_items


def test_missing_karina_assets_disable_the_widget(tk_root, tmp_path) -> None:
    mascot = KarinaMascotView(tk_root, tmp_path)

    assert not mascot.enabled
    mascot.start()
    assert mascot._float_job is None


def test_karina_static_mode_has_no_idle_animation_loops(tk_root) -> None:
    mascot = KarinaMascotView(tk_root, PROJECT_ROOT / "assets")
    mascot.set_animation_mode("static")
    mascot.start()

    assert mascot._float_job is None
    assert mascot._expression_job is None
    assert mascot._greet_job is None
    mascot.stop()


def test_missing_working_assets_keep_idle_available(tk_root, tmp_path) -> None:
    source = PROJECT_ROOT / "assets" / "mascot" / "karina"
    target = tmp_path / "mascot" / "karina"
    for folder, files in (
        ("idle", KarinaMascotView._IDLE_FILES),
        ("greet", KarinaMascotView._GREET_FILES),
        ("common", ("shadow.png",)),
    ):
        destination = target / folder
        destination.mkdir(parents=True, exist_ok=True)
        for name in files:
            copy2(source / folder / name, destination / name)

    mascot = KarinaMascotView(tk_root, tmp_path)

    assert mascot.enabled
    assert mascot._working_frames == ()
    mascot.start()
    mascot.begin_working()
    assert mascot._working_count == 1
    mascot.finish_working("success")
    assert mascot._working_count == 0
    mascot.stop()


def test_existing_task_result_semantics_map_to_reactions() -> None:
    class Value:
        def __init__(self, *, success=True, cancelled=False, warning_count=0, status=""):
            self.success = success
            self.cancelled = cancelled
            self.warning_count = warning_count
            self.status = status

    class Task:
        def __init__(self, success=True, value=None):
            self.success = success
            self.value = value

    assert classify_mascot_outcome(Task(False)) == "error"
    assert classify_mascot_outcome(Task(value=Value(cancelled=True))) is None
    assert classify_mascot_outcome(Task(value=Value(success=False))) == "error"
    assert classify_mascot_outcome(Task(value=Value(warning_count=1))) == "warning"
    assert classify_mascot_outcome(
        Task(value=Value(status="PARTIAL_SUCCESS")),
        warning_statuses=("PARTIAL_SUCCESS",),
    ) == "warning"
    assert classify_mascot_outcome(Task(value=Value())) == "success"
