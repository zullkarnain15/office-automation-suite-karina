"""Asynchronous, idempotent daily Finger Monitoring report via Outlook Classic."""

from __future__ import annotations

import html
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

JAKARTA = timezone(timedelta(hours=7), name="Asia/Jakarta")


@dataclass(frozen=True, slots=True)
class DailyEmailSnapshot:
    cycle_id: int
    report_date: str
    checked_at: str
    total: int
    online: int
    offline: int
    unverifiable: int
    alert: int
    offline_devices: tuple[dict, ...]


class OutlookClassicSender:
    """Minimal new-mail sender; it never adds an attachment."""

    def send_html(self, recipient: str, subject: str, body_html: str) -> None:
        import win32com.client  # type: ignore[import-not-found]

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)
        mail.To = recipient
        mail.Subject = subject
        mail.HTMLBody = body_html
        mail.Send()


class DailyEmailReportService:
    def __init__(self, repository, *, sender=None, activity_gate=None, now=None) -> None:
        self.repository = repository
        self.sender = sender or OutlookClassicSender()
        self.activity_gate = activity_gate
        self.now = now or (lambda: datetime.now(JAKARTA))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oas-k-finger-email")
        self._lock = threading.Lock()
        self._accepting = True

    def consider_cycle(self, cycle_id: int, source: str, cycle_status: str) -> bool:
        if source not in {"AUTO", "CHECK_ALL"} or cycle_status != "COMPLETED":
            return False
        current = self.now().astimezone(JAKARTA)
        settings = self.repository.get_settings()
        hour, minute = (int(value) for value in settings["daily_report_start"].split(":"))
        if (current.hour, current.minute) < (hour, minute):
            return False
        try:
            snapshot = self.snapshot(cycle_id, report_date=current.date().isoformat())
        except ValueError:
            return False
        completed = datetime.fromisoformat(snapshot.checked_at)
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=JAKARTA)
        else:
            completed = completed.astimezone(JAKARTA)
        if completed.date() != current.date() or (completed.hour, completed.minute) < (hour, minute):
            return False
        recipient = str(settings["recipient_email"]).strip()
        try:
            delivery_id = self.repository.reserve_email_delivery(
                snapshot.report_date, cycle_id, recipient
            )
        except sqlite3.IntegrityError:
            return False
        return self._submit(delivery_id, recipient, snapshot)

    def retry_failed(self, report_date: str | None = None) -> bool:
        current = self.now().astimezone(JAKARTA)
        date_value = report_date or current.date().isoformat()
        delivery = self.repository.email_delivery_for_date(date_value)
        if delivery is None or delivery["status"] != "FAILED":
            return False
        recipient = str(self.repository.get_settings()["recipient_email"]).strip()
        snapshot = self.snapshot(int(delivery["cycle_id"]), report_date=date_value)
        delivery_id = self.repository.reserve_failed_email_retry(
            date_value, snapshot.cycle_id, recipient
        )
        return self._submit(delivery_id, recipient, snapshot)

    def snapshot(self, cycle_id: int, *, report_date: str) -> DailyEmailSnapshot:
        with self.repository.factory.connect(self.repository.database_path, read_only=True) as connection:
            cycle = connection.execute(
                "SELECT * FROM check_cycle WHERE cycle_id=?", (int(cycle_id),)
            ).fetchone()
            if cycle is None or cycle["status"] != "COMPLETED" or cycle["trigger_source"] not in {"AUTO", "CHECK_ALL"}:
                raise ValueError("Cycle tidak memenuhi syarat laporan harian.")
            rows = tuple(dict(row) for row in connection.execute(
                """SELECT d.branch_name,d.ip_address,r.status,r.offline_observed_days
                   FROM check_result r JOIN device_master d ON d.device_id=r.device_id
                   WHERE r.cycle_id=? ORDER BY r.result_id""",
                (int(cycle_id),),
            ))
            if len(rows) != int(cycle["requested_devices"]):
                raise ValueError("Cycle tidak lengkap dan tidak boleh dikirim.")
        offline = tuple(sorted(
            (row for row in rows if row["status"] == "OFFLINE"),
            key=lambda row: (-int(row["offline_observed_days"]), row["branch_name"].casefold()),
        ))
        unverifiable = sum(row["status"] in {"UNKNOWN", "ERROR", "NETWORK_UNREACHABLE"} for row in rows)
        threshold = int(self.repository.get_settings()["offline_alert_observed_dates"])
        return DailyEmailSnapshot(
            int(cycle_id), report_date, str(cycle["completed_at"] or cycle["started_at"]),
            len(rows), sum(row["status"] == "ONLINE" for row in rows), len(offline),
            unverifiable, sum(int(row["offline_observed_days"]) >= threshold for row in offline), offline,
        )

    def _submit(self, delivery_id: int, recipient: str, snapshot: DailyEmailSnapshot) -> bool:
        with self._lock:
            if not self._accepting:
                self.repository.update_email_delivery(
                    delivery_id,
                    "FAILED",
                    error_detail="Aplikasi sedang ditutup; pengiriman tidak dijalankan.",
                )
                return False
            self._executor.submit(self._send_reserved, delivery_id, recipient, snapshot)
        return True

    def _send_reserved(self, delivery_id: int, recipient: str, snapshot: DailyEmailSnapshot) -> None:
        try:
            if not recipient:
                raise ValueError("Recipient Email belum diisi.")
            context = self.activity_gate.activity("EMAIL") if self.activity_gate else _null_context()
            with context, _com_initialized():
                self.sender.send_html(
                    recipient,
                    f"[OAS-K] Finger Monitoring - {snapshot.offline} Devices Offline",
                    self.build_html(snapshot),
                )
            self.repository.update_email_delivery(delivery_id, "SENT")
        except Exception as exc:
            self.repository.update_email_delivery(delivery_id, "FAILED", error_detail=str(exc))

    @staticmethod
    def build_html(snapshot: DailyEmailSnapshot) -> str:
        summary = (
            f"<p>Check time: {html.escape(snapshot.checked_at)}</p>"
            f"<p>Total: {snapshot.total} | Online: {snapshot.online} | Offline: {snapshot.offline} | "
            f"Unknown/Error: {snapshot.unverifiable} | Alert &ge;3 days: {snapshot.alert}</p>"
        )
        if snapshot.offline_devices:
            rows = "".join(
                f"<tr><td>{html.escape(str(row['branch_name']))}</td><td>{html.escape(str(row['ip_address']))}</td><td>{int(row['offline_observed_days'])}</td></tr>"
                for row in snapshot.offline_devices
            )
            detail = "<table border='1' cellpadding='4'><tr><th>Branch</th><th>IP</th><th>Observed Offline Days</th></tr>" + rows + "</table>"
        else:
            detail = "<p><b>All Devices Online</b></p>" if not snapshot.unverifiable else ""
        warning = "<p><b>Some devices could not be verified. Review UNKNOWN/ERROR/NETWORK_UNREACHABLE results.</b></p>" if snapshot.unverifiable else ""
        return "<html><body><h3>OAS-K Finger Monitoring</h3>" + summary + detail + warning + "</body></html>"

    def shutdown(self) -> None:
        with self._lock:
            self._accepting = False
        self._executor.shutdown(wait=False, cancel_futures=True)


@contextmanager
def _com_initialized():
    pythoncom = None
    try:
        import pythoncom as module  # type: ignore[import-not-found]
        pythoncom = module
        pythoncom.CoInitialize()
    except ImportError:
        pass
    try:
        yield
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()


@contextmanager
def _null_context():
    yield
