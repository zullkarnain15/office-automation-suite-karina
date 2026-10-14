from datetime import date, time

from utilities.attendance_reconciliation.normalizer import interpret_single_tap
from utilities.attendance_reconciliation.normalizer import normalize_date
from utilities.attendance_reconciliation.normalizer import normalize_nik
from utilities.attendance_reconciliation.normalizer import normalize_time


def test_normalize_nik_preserves_leading_zero_and_removes_excel_suffix() -> None:
    assert normalize_nik(" 001234567 ") == "001234567"
    assert normalize_nik("001234567.0") == "001234567"
    assert normalize_nik(123456789.0) == "123456789"


def test_normalize_date_uses_unambiguous_project_formats() -> None:
    assert normalize_date("07/14/2026") == date(2026, 7, 14)
    assert normalize_date("2026-07-14") == date(2026, 7, 14)
    assert normalize_date("14/07/2026") is None


def test_normalize_time_supports_text_and_excel_fraction() -> None:
    assert normalize_time("08:30") == time(8, 30)
    assert normalize_time(0.5) == time(12, 0)


def test_single_tap_at_noon_becomes_time_in() -> None:
    machine_in, machine_out, original, column, rule, status = (
        interpret_single_tap("12:00", None)
    )
    assert (machine_in, machine_out) == (time(12, 0), None)
    assert original == time(12, 0)
    assert column == "Jam Masuk"
    assert rule == "TIME_LE_12_AS_IN"
    assert status == "SINGLE_TAP_IN"


def test_single_tap_after_noon_becomes_time_out() -> None:
    machine_in, machine_out, _, _, rule, status = interpret_single_tap(
        None, "18:15"
    )
    assert (machine_in, machine_out) == (None, time(18, 15))
    assert rule == "TIME_GT_12_AS_OUT"
    assert status == "SINGLE_TAP_OUT"


def test_single_tap_invalid_when_no_valid_single_time() -> None:
    assert interpret_single_tap(None, None)[-1] == "INVALID_SINGLE_TAP_TIME"
    assert (
        interpret_single_tap("08:00", "17:00")[-1]
        == "INVALID_SINGLE_TAP_TIME"
    )
