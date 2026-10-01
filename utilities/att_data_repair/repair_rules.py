"""Deterministic Att Data Repair business rules."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import replace
from datetime import date, time
from typing import Any

from utilities.att_data_repair.models import (
    AttDataRepairRequest,
    FinalRecord,
    NormalizedRecord,
    RepairAnomaly,
    RepairChange,
)
from utilities.att_data_repair.normalizer import (
    format_date,
    format_time,
    minutes_from_time,
    time_from_minutes,
)
from utilities.att_data_repair.statuses import AnomalyCode, ChangeCode, FinalStatus


def apply_repair_rules(
    record: NormalizedRecord,
    request: AttDataRepairRequest,
    *,
    current_year: int | None = None,
) -> tuple[FinalRecord | None, RepairAnomaly | None, tuple[RepairChange, ...]]:
    """Apply Sprint 2 repair rules to one normalized record."""

    anomaly = _identity_anomaly(record)
    if anomaly is not None:
        return None, anomaly, ()

    assert record.workflow is not None
    changes: list[RepairChange] = []
    record, nik_anomaly = _repair_nik(record, changes)
    if nik_anomaly is not None:
        return None, nik_anomaly, tuple(changes)

    anomaly = _date_parse_anomaly(record)
    if anomaly is not None:
        return None, anomaly, tuple(changes)

    assert record.date_in is not None
    record, year_anomaly = _align_year_to_current(
        record,
        current_year or date.today().year,
        changes,
    )
    if year_anomaly is not None:
        return None, year_anomaly, tuple(changes)

    anomaly = _date_policy_anomaly(record, request)
    if anomaly is not None:
        return None, anomaly, tuple(changes)

    final_date_out = record.date_in
    if record.date_out != record.date_in:
        changes.append(
            _change(
                record,
                "Date_Out",
                format_date(record.date_out),
                format_date(final_date_out),
                ChangeCode.DATE_OUT_ALIGNED_TO_DATE_IN,
                "Date_Out final mengikuti Date_In karena OAS-K tidak mendukung night shift.",
            )
        )

    _time_format_changes(record, changes)
    final_in, final_out = _repair_times(record, request, changes)
    duration = minutes_from_time(final_out) - minutes_from_time(final_in)
    if duration < request.minimum_duration_minutes or duration <= 0:
        default_in, default_out = _default_pair(record.date_in, request)
        final_in, final_out = default_in, default_out
        duration = minutes_from_time(final_out) - minutes_from_time(final_in)
        _append_default_pair_changes(
            record,
            changes,
            final_in,
            final_out,
            "Final time tidak logis setelah repair; pasangan default digunakan.",
        )

    final_status = (
        FinalStatus.REPAIRED
        if changes
        else FinalStatus.VALID_UNCHANGED
    )
    final_record = FinalRecord(
        record_id=record.record_id,
        workflow=record.workflow,
        nik=record.nik,
        date_in=record.date_in,
        time_in=final_in,
        date_out=final_date_out,
        time_out=final_out,
        duration_minutes=duration,
        source_sheet=record.source.source_sheet,
        source_file=record.source.source_file,
        source_row=record.source.source_row,
        final_status=str(final_status),
        changes=tuple(changes),
    )
    return final_record, None, tuple(changes)


def _identity_anomaly(record: NormalizedRecord) -> RepairAnomaly | None:
    if AnomalyCode.INVALID_WORKFLOW in record.invalid_codes:
        return _anomaly(
            record,
            AnomalyCode.INVALID_WORKFLOW,
            "Workflow kosong atau tidak valid.",
        )
    if AnomalyCode.INVALID_NIK in record.invalid_codes:
        return _anomaly(record, AnomalyCode.INVALID_NIK, "NIK kosong atau error.")
    return None


def _date_parse_anomaly(record: NormalizedRecord) -> RepairAnomaly | None:
    if AnomalyCode.INVALID_DATE in record.invalid_codes or record.date_in is None:
        return _anomaly(
            record,
            AnomalyCode.INVALID_DATE,
            "Date_In invalid atau tidak dapat dipastikan.",
        )
    return None


def _repair_nik(
    record: NormalizedRecord,
    changes: list[RepairChange],
) -> tuple[NormalizedRecord, RepairAnomaly | None]:
    nik = record.nik
    if not nik.isascii() or not nik.isdigit():
        return record, _anomaly(
            record,
            AnomalyCode.INVALID_NIK,
            "NIK harus berisi digit ASCII tanpa huruf, desimal, atau notasi ilmiah.",
        )

    if len(nik) == 9:
        return record, None

    if len(nik) == 10:
        leading_zeros = _zero_run(nik)
        if 5 <= leading_zeros <= 8:
            return _replace_nik(
                record,
                f"2{nik}",
                ChangeCode.NIK_LEADING_TWO_RESTORED,
                "NIK 10 digit dengan 5-8 nol awal diperbaiki dengan menambahkan angka 2.",
                changes,
            )

        if nik.startswith("2"):
            zeros_after_two = _zero_run(nik, start=1)
            if 4 <= zeros_after_two <= 7:
                return _replace_nik(
                    record,
                    f"{nik[:1]}0{nik[1:]}",
                    ChangeCode.NIK_MISSING_ZERO_RESTORED,
                    "NIK 10 digit pola panjang diperbaiki dengan menambahkan satu nol setelah angka 2.",
                    changes,
                )
            if zeros_after_two == 3:
                return _replace_nik(
                    record,
                    nik[1:],
                    ChangeCode.NIK_EXTRA_LEADING_TWO_REMOVED,
                    "NIK 9 digit yang mendapat tambahan angka 2 dikembalikan ke pola 9 digit.",
                    changes,
                )
        return record, None

    if len(nik) == 11:
        if _is_valid_long_nik(nik):
            return record, None
        leading_zeros = _zero_run(nik)
        if 6 <= leading_zeros <= 9:
            candidate = f"2{nik[1:]}"
            if _is_valid_long_nik(candidate):
                return _replace_nik(
                    record,
                    candidate,
                    ChangeCode.NIK_LEADING_TWO_REPLACED,
                    "Nol pertama NIK 11 digit diganti menjadi angka 2 sesuai pola NIK panjang.",
                    changes,
                )
        return record, _anomaly(
            record,
            AnomalyCode.INVALID_NIK,
            "Pola NIK 11 digit tidak sesuai pola panjang 2 diikuti 5-8 nol.",
        )

    return record, _anomaly(
        record,
        AnomalyCode.INVALID_NIK,
        "Panjang NIK harus tepat 9, 10, atau 11 digit.",
    )


def _replace_nik(
    record: NormalizedRecord,
    candidate: str,
    code: ChangeCode,
    reason: str,
    changes: list[RepairChange],
) -> tuple[NormalizedRecord, None]:
    changes.append(_change(record, "NIK", record.nik, candidate, code, reason))
    return replace(record, nik=candidate), None


def _zero_run(value: str, *, start: int = 0) -> int:
    count = 0
    for character in value[start:]:
        if character != "0":
            break
        count += 1
    return count


def _is_valid_long_nik(nik: str) -> bool:
    return len(nik) == 11 and nik.startswith("2") and 5 <= _zero_run(nik, start=1) <= 8


def _date_policy_anomaly(
    record: NormalizedRecord,
    request: AttDataRepairRequest,
) -> RepairAnomaly | None:
    assert record.date_in is not None
    if not (request.period_start <= record.date_in <= request.period_end):
        return _anomaly(
            record,
            AnomalyCode.OUTSIDE_REPORT_PERIOD,
            "Date_In berada di luar periode report.",
        )
    if record.date_in.weekday() == 6 and not _is_month_end(record.date_in):
        return _anomaly(
            record,
            AnomalyCode.SUNDAY_NOT_MONTH_END,
            "Hari Minggu dikeluarkan kecuali merupakan hari terakhir bulan.",
        )
    return None


def _align_year_to_current(
    record: NormalizedRecord,
    current_year: int,
    changes: list[RepairChange],
) -> tuple[NormalizedRecord, RepairAnomaly | None]:
    assert record.date_in is not None
    aligned_dates: dict[str, date | None] = {}
    for field_name, value in (
        ("Date_In", record.date_in),
        ("Date_Out", record.date_out),
    ):
        if value is None or value.year == current_year:
            aligned_dates[field_name] = value
            continue
        try:
            aligned = value.replace(year=current_year)
        except ValueError:
            return record, _anomaly(
                record,
                AnomalyCode.INVALID_DATE,
                f"{field_name} tidak valid setelah tahun diselaraskan ke {current_year}.",
            )
        aligned_dates[field_name] = aligned
        changes.append(
            _change(
                record,
                field_name,
                format_date(value),
                format_date(aligned),
                ChangeCode.DATE_YEAR_ALIGNED_TO_CURRENT_YEAR,
                f"Tahun tanggal diselaraskan ke tahun berjalan {current_year}.",
            )
        )
    return (
        replace(
            record,
            date_in=aligned_dates["Date_In"],
            date_out=aligned_dates["Date_Out"],
        ),
        None,
    )


def _is_month_end(value: date) -> bool:
    return value.day == monthrange(value.year, value.month)[1]


def _repair_times(
    record: NormalizedRecord,
    request: AttDataRepairRequest,
    changes: list[RepairChange],
) -> tuple[time, time]:
    default_in, default_out = _default_pair(record.date_in, request)
    in_value = record.time_in
    out_value = record.time_out

    if in_value == time.min:
        in_value = default_in
        changes.append(
            _change(
                record,
                "Time_In",
                "00:00",
                format_time(in_value),
                ChangeCode.MIDNIGHT_TIME_IN_DEFAULTED,
                "Time_In 00:00 diganti dengan jam masuk default hari.",
            )
        )
    if out_value == time.min:
        out_value = request.midnight_time_out_default
        changes.append(
            _change(
                record,
                "Time_Out",
                "00:00",
                format_time(out_value),
                ChangeCode.MIDNIGHT_TIME_OUT_DEFAULTED,
                "Time_Out 00:00 diganti dengan konfigurasi midnight_time_out_default.",
            )
        )

    if record.date_in.weekday() == 5 and _is_blank(record.source.time_out_raw):
        saturday_out = request.saturday_missing_out_default
        if in_value is None:
            in_value = default_in
            changes.append(
                _change(
                    record,
                    "Time_In",
                    format_time(record.time_in),
                    format_time(in_value),
                    ChangeCode.DEFAULT_TIME_APPLIED,
                    "Time_In invalid; jam masuk default Sabtu digunakan.",
                )
            )
        in_min = minutes_from_time(in_value)
        out_min = minutes_from_time(saturday_out)
        if out_min <= in_min or out_min - in_min < request.minimum_duration_minutes:
            out_min = in_min + request.minimum_duration_minutes
        if out_min <= 1439:
            out_value = time_from_minutes(out_min)
            changes.append(
                _change(
                    record,
                    "Time_Out",
                    format_time(record.time_out),
                    format_time(out_value),
                    ChangeCode.SATURDAY_MISSING_OUT_DEFAULTED,
                    "Time_Out Sabtu kosong; konfigurasi Sabtu digunakan dengan guard durasi minimum.",
                )
            )

    if in_value is not None and out_value is not None:
        in_min = minutes_from_time(in_value)
        out_min = minutes_from_time(out_value)
        if in_min > out_min:
            in_value, out_value = out_value, in_value
            changes.append(
                _change(
                    record,
                    "Time_In",
                    format_time(record.time_in),
                    format_time(in_value),
                    ChangeCode.TIME_IN_OUT_SWAPPED,
                    "Time_In lebih besar dari Time_Out; jam ditukar.",
                )
            )
            changes.append(
                _change(
                    record,
                    "Time_Out",
                    format_time(record.time_out),
                    format_time(out_value),
                    ChangeCode.TIME_IN_OUT_SWAPPED,
                    "Time_In lebih besar dari Time_Out; jam ditukar.",
                )
            )
            in_min, out_min = out_min, in_min
        if out_min - in_min < request.minimum_duration_minutes:
            adjusted = in_min + request.minimum_duration_minutes
            if adjusted > 1439:
                _append_default_pair_changes(
                    record,
                    changes,
                    default_in,
                    default_out,
                    "Minimum duration melewati 23:59; pasangan default digunakan.",
                )
                return default_in, default_out
            out_value = time_from_minutes(adjusted)
            changes.append(
                _change(
                    record,
                    "Time_Out",
                    format_time(record.time_out),
                    format_time(out_value),
                    ChangeCode.MINIMUM_DURATION_APPLIED,
                    "Durasi kurang dari minimum; Time_Out disesuaikan.",
                )
            )
        return in_value, out_value

    if in_value is not None:
        in_min = minutes_from_time(in_value)
        out_min = minutes_from_time(default_out)
        if out_min <= in_min or out_min - in_min < request.minimum_duration_minutes:
            out_min = in_min + request.minimum_duration_minutes
        if out_min > 1439:
            _append_default_pair_changes(
                record,
                changes,
                default_in,
                default_out,
                "Perbaikan Time_Out melewati 23:59; pasangan default digunakan.",
            )
            return default_in, default_out
        out_value = time_from_minutes(out_min)
        changes.append(
            _change(
                record,
                "Time_Out",
                format_time(record.time_out),
                format_time(out_value),
                ChangeCode.PARTIAL_TIME_REPAIRED,
                "Time_Out invalid; diperbaiki dari default/durasi minimum.",
            )
        )
        return in_value, out_value

    if out_value is not None:
        out_min = minutes_from_time(out_value)
        in_min = minutes_from_time(default_in)
        if in_min >= out_min or out_min - in_min < request.minimum_duration_minutes:
            in_min = out_min - request.minimum_duration_minutes
        if in_min < 0:
            _append_default_pair_changes(
                record,
                changes,
                default_in,
                default_out,
                "Perbaikan Time_In kurang dari 00:00; pasangan default digunakan.",
            )
            return default_in, default_out
        in_value = time_from_minutes(in_min)
        changes.append(
            _change(
                record,
                "Time_In",
                format_time(record.time_in),
                format_time(in_value),
                ChangeCode.PARTIAL_TIME_REPAIRED,
                "Time_In invalid; diperbaiki dari default/durasi minimum.",
            )
        )
        return in_value, out_value

    _append_default_pair_changes(
        record,
        changes,
        default_in,
        default_out,
        "Kedua jam invalid; pasangan default digunakan.",
    )
    return default_in, default_out


def _default_pair(
    record_date: date,
    request: AttDataRepairRequest,
) -> tuple[time, time]:
    weekday = record_date.weekday()
    if weekday < 5:
        return request.weekday_default_in, request.weekday_default_out
    if weekday == 5:
        return request.saturday_default_in, request.saturday_default_out
    return request.sunday_invalid_default_in, request.sunday_invalid_default_out


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _time_format_changes(
    record: NormalizedRecord,
    changes: list[RepairChange],
) -> None:
    for field_name, meta in (
        ("Time_In", record.time_in_meta),
        ("Time_Out", record.time_out_meta),
    ):
        if meta is None or not meta.normalized or meta.value is None:
            continue
        changes.append(
            _change(
                record,
                field_name,
                str(meta.original_value).strip(),
                format_time(meta.value),
                ChangeCode.TIME_FORMAT_NORMALIZED,
                "Format jam dinormalisasi ke HH:MM.",
            )
        )


def _append_default_pair_changes(
    record: NormalizedRecord,
    changes: list[RepairChange],
    final_in: time,
    final_out: time,
    reason: str,
) -> None:
    changes.append(
        _change(
            record,
            "Time_In",
            format_time(record.time_in),
            format_time(final_in),
            ChangeCode.DEFAULT_TIME_APPLIED,
            reason,
        )
    )
    changes.append(
        _change(
            record,
            "Time_Out",
            format_time(record.time_out),
            format_time(final_out),
            ChangeCode.DEFAULT_TIME_APPLIED,
            reason,
        )
    )


def _change(
    record: NormalizedRecord,
    field_name: str,
    original: str,
    final: str,
    code: ChangeCode,
    reason: str,
) -> RepairChange:
    return RepairChange(
        record_id=record.record_id,
        field_name=field_name,
        original_value=original,
        final_value=final,
        change_code=str(code),
        reason=reason,
    )


def _anomaly(
    record: NormalizedRecord,
    code: AnomalyCode,
    reason: str,
) -> RepairAnomaly:
    return RepairAnomaly(
        record_id=record.record_id,
        anomaly_code=str(code),
        reason=reason,
        action="EXCLUDED_FROM_FINAL_RECORDS",
        source=record.source,
    )
