"""HRIS UI6 orchestration, validation, intervention, and audit lifecycle."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from shared.database import SQLiteConnectionFactory
from shared.database.models import JobFileRecord, JobHistoryRecord
from shared.database.repositories import GlobalSettingsRepository, JobRepository
from shared.database.time_utils import current_timestamp
from shared.storage.path_resolver import get_hris_recorder_profiles_root
from ui.hris_models import (
    HRISCancellationToken,
    HRISDefaults,
    HRISInteractionGate,
    HRISJobState,
    HRISProgressEvent,
    HRISResolvedRequest,
    HRISRunRequest,
    HRISRunResult,
)
from ui.services.module_configuration_service import ModuleConfigurationService


_TERMINAL = {"COMPLETED", "COMPLETED_WITH_WARNING", "FAILED", "CANCELLED"}


class HRISService:
    def __init__(self, storage_service, adapter) -> None:
        self.storage_service = storage_service
        self.adapter = adapter
        self.factory = SQLiteConnectionFactory()
        self.module_configurations = ModuleConfigurationService(self.factory)
        self._gates: dict[str, HRISInteractionGate] = {}

    def load_active_configuration(self):
        defaults = self.load_defaults()
        summaries = self.module_configurations.load_summaries(defaults.database_path)
        return next(item for item in summaries if item.module == "HRIS")

    def load_defaults(self) -> HRISDefaults:
        storage = self.storage_service.resolve_status()
        database = storage.database_path
        if not storage.database_valid or database is None or storage.data_root is None:
            return HRISDefaults(
                False,
                database,
                storage.data_root,
                warning=(
                    "Data Location/database belum tersedia. Siapkan melalui Settings; "
                    "database tidak dibuat otomatis."
                ),
            )
        with self.factory.connect(database, read_only=True) as connection:
            global_value = GlobalSettingsRepository(connection).get_global_settings()
            settings = connection.execute(
                "SELECT * FROM hris_settings WHERE hris_settings_id=1"
            ).fetchone()
            controls = connection.execute(
                "SELECT workflow, run_control_id FROM hris_run_controls "
                "WHERE is_active=1 ORDER BY workflow, sequence"
            ).fetchall()
            steps = connection.execute(
                "SELECT COUNT(*) FROM hris_assisted_steps WHERE is_active=1"
            ).fetchone()[0]
        ho = tuple(str(row["run_control_id"]) for row in controls if row["workflow"] == "HO")
        branch = tuple(
            str(row["run_control_id"])
            for row in controls
            if row["workflow"] == "BRANCH"
        )
        return HRISDefaults(
            True,
            database,
            storage.data_root,
            str(settings["hris_url"]) if settings else "",
            str(settings["browser_channel"]) if settings else "msedge",
            Path(global_value.output_root)
            if global_value and global_value.output_root
            else storage.output_folder,
            bool(settings and settings["use_global_period"]),
            global_value.period_start if global_value else None,
            global_value.period_end if global_value else None,
            Path(settings["click_profile_path"])
            if settings and settings["click_profile_path"]
            else None,
            ho,
            branch,
            int(steps),
            str(settings["updated_at"]) if settings else None,
        )

    def discover_txt(self, folder: Path) -> tuple[Path, ...]:
        if not folder.is_dir():
            raise ValueError("Folder TXT Attendance tidak tersedia.")
        return tuple(sorted(folder.glob("*.txt"), key=lambda item: item.name.casefold()))

    def resolve_request(self, request: HRISRunRequest) -> HRISResolvedRequest:
        defaults = self.load_defaults()
        if not defaults.database_available or not defaults.database_path or not defaults.data_root:
            raise RuntimeError(defaults.warning)
        workflow = request.workflow.upper()
        if workflow not in {"HO", "BRANCH"}:
            raise ValueError("Workflow harus HO atau BRANCH.")
        if not request.manual_upload_acknowledged:
            raise ValueError("Konfirmasi automation klik HRIS wajib dicentang.")
        username = (request.login_id or "").strip()
        password = request.login_secret or ""
        if not request.manual_login:
            if not username:
                raise ValueError("Username HRIS wajib diisi untuk Auto Login.")
            if not password:
                raise ValueError("Password HRIS wajib diisi untuk Auto Login.")
        source = request.source_folder.expanduser()
        files = self.discover_txt(source)
        if not files:
            raise ValueError("Folder tidak memiliki file TXT.")
        if request.use_global_period:
            start, end = defaults.global_period_start, defaults.global_period_end
            if not defaults.use_global_period or not start or not end:
                raise ValueError("Global period HRIS belum tersedia.")
        else:
            start, end = request.period_start, request.period_end
        self._validate_period(start, end)
        profile = request.recorder_profile or defaults.recorder_profile
        if profile is None:
            raise ValueError("Recorder profile HRIS wajib dipilih.")
        if profile.is_absolute() or ".." in profile.parts:
            raise ValueError("Recorder profile harus berupa relative path yang aman.")
        if not profile.parts or profile.parts[:2] != ("recorder_profiles", "hris"):
            raise ValueError("Recorder profile harus berada di recorder_profiles/hris.")
        output = defaults.output_root
        if output is None:
            raise ValueError("Global Output Root belum tersedia.")
        self._validate_output_parent(output)
        configuration = request.configuration_path
        if configuration is not None:
            if configuration.suffix.casefold() != ".xlsx" or not configuration.is_file():
                raise ValueError("Fallback HRIS harus berupa workbook .xlsx yang tersedia.")
        return HRISResolvedRequest(
            self._new_job_id(),
            defaults.database_path,
            defaults.data_root,
            configuration,
            source,
            output,
            workflow,
            str(start),
            str(end),
            request.use_global_period,
            profile,
            request.manual_login,
            username if not request.manual_login else None,
            password if not request.manual_login else None,
        )

    def preflight(self, request: HRISRunRequest):
        resolved = self.resolve_request(request)
        return resolved, self.adapter.validate(resolved)

    def calibrate_profile(
        self,
        workflow: str,
        *,
        instruction_callback,
        coordinate_callback,
    ) -> Path:
        defaults = self.load_defaults()
        if not defaults.database_available or not defaults.database_path or not defaults.data_root:
            raise RuntimeError(defaults.warning or "Database HRIS belum tersedia.")
        workflow_value = workflow.upper()
        if workflow_value not in {"HO", "BRANCH"}:
            raise ValueError("Workflow harus HO atau BRANCH.")

        relative = defaults.recorder_profile
        if (
            relative is None
            or relative.is_absolute()
            or ".." in relative.parts
            or tuple(relative.parts[:2]) != ("recorder_profiles", "hris")
        ):
            relative = Path("recorder_profiles") / "hris" / (
                f"hris_{workflow_value.lower()}_click_profile.json"
            )
        target = defaults.data_root / relative
        official_root = get_hris_recorder_profiles_root(defaults.data_root).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.resolve().relative_to(official_root)
        except ValueError as exc:
            raise ValueError(
                "Recorder profile harus berada di recorder_profiles/hris."
            ) from exc

        saved = self.adapter.calibrate_profile(
            defaults.database_path,
            target,
            instruction_callback=instruction_callback,
            coordinate_callback=coordinate_callback,
        )
        saved_relative = saved.resolve().relative_to(defaults.data_root.resolve())
        stored = saved_relative.as_posix()
        with self.factory.connect(defaults.database_path) as connection:
            connection.execute(
                """
                UPDATE hris_settings
                SET click_profile_path = ?, updated_at = ?
                WHERE hris_settings_id = 1
                """,
                (stored, current_timestamp()),
            )
        return Path(stored)

    def run_job(
        self,
        resolved: HRISResolvedRequest,
        *,
        cancellation: HRISCancellationToken,
        progress,
        log,
        intervention,
    ) -> HRISRunResult:
        started = current_timestamp()
        gate = HRISInteractionGate()
        self._gates[resolved.job_id] = gate
        with self.factory.connect(resolved.database_path) as connection:
            repository = JobRepository(connection)
            job_pk = repository.create_job(
                JobHistoryRecord(
                    job_id=resolved.job_id,
                    module_code="HRIS",
                    workflow=resolved.workflow,
                    unified_status="PENDING",
                    output_path_used=str(resolved.output_root),
                    period_start_used=resolved.period_start,
                    period_end_used=resolved.period_end,
                    used_global_output=True,
                    used_global_period=resolved.used_global_period,
                    source_summary=self._source_summary(resolved),
                    created_at=started,
                    started_at=started,
                )
            )
            for source in self.discover_txt(resolved.source_folder):
                repository.add_job_file(
                    JobFileRecord(
                        job_pk,
                        "SOURCE_TXT",
                        str(source),
                        started,
                        file_size=source.stat().st_size,
                        last_checked_at=started,
                    )
                )
            repository.update_job_status(
                module_code="HRIS",
                job_id=resolved.job_id,
                unified_status="RUNNING",
                phase="BROWSER_STARTED",
                message="HRIS worker started.",
            )

        def audited_progress(event: HRISProgressEvent) -> None:
            progress(event)
            status = self._unified_status(event.state)
            if status in _TERMINAL:
                return
            with self.factory.connect(resolved.database_path) as connection:
                JobRepository(connection).update_job_status(
                    module_code="HRIS",
                    job_id=resolved.job_id,
                    unified_status=status,
                    legacy_status=event.state,
                    phase=event.state,
                    message=event.message,
                )

        try:
            result = self.adapter.run(
                resolved,
                cancellation=cancellation,
                gate=gate,
                progress=audited_progress,
                log=log,
                intervention=intervention,
            )
        finally:
            self._gates.pop(resolved.job_id, None)
        final = "CANCELLED" if result.cancelled else "COMPLETED" if result.success else "FAILED"
        with self.factory.connect(resolved.database_path) as connection:
            repository = JobRepository(connection)
            repository.finish_job(
                module_code="HRIS",
                job_id=resolved.job_id,
                unified_status=final,
                finished_at=result.ended_at,
                success_count=sum(item.status == "SUCCESS" for item in result.files),
                failed_count=sum(item.status != "SUCCESS" for item in result.files),
                error_message=result.error_summary,
                legacy_status=final,
            )
            repository.update_job_artifacts(
                job_pk,
                summary_json_path=str(result.summary_json_path)
                if result.summary_json_path
                else None,
                process_log_path=str(result.process_log_path)
                if result.process_log_path
                else None,
                source_summary=self._source_summary(resolved, result),
            )
            self._record_result_files(repository, job_pk, result)
        return result

    def confirm_login_complete(self, job_id: str) -> None:
        self._gate(job_id).confirm_login()

    def confirm_upload_complete(self, job_id: str) -> None:
        self._gate(job_id).confirm_upload()

    def report_upload_failed(self, job_id: str, message: str) -> None:
        self._gate(job_id).fail_upload(message)

    def choose_intervention(self, job_id: str, action: str) -> None:
        gate = self._gate(job_id)
        allowed = (
            set(gate.current_intervention.actions)
            if gate.current_intervention is not None
            else set()
        )
        if action not in allowed:
            raise ValueError(f"Tindakan intervensi HRIS tidak valid: {action}")
        gate.choose(action)

    def request_cancel(
        self,
        resolved: HRISResolvedRequest,
        token: HRISCancellationToken,
    ) -> None:
        token.request()
        gate = self._gates.get(resolved.job_id)
        if gate:
            gate.login_event.set()
            gate.upload_event.set()
            gate.decision_event.set()
        with self.factory.connect(resolved.database_path) as connection:
            row = connection.execute(
                "SELECT unified_status FROM job_history WHERE module_code='HRIS' AND job_id=?",
                (resolved.job_id,),
            ).fetchone()
            if row and row["unified_status"] not in _TERMINAL:
                JobRepository(connection).update_job_status(
                    module_code="HRIS",
                    job_id=resolved.job_id,
                    unified_status="PAUSED",
                    legacy_status="CANCEL_REQUESTED",
                    phase="CANCEL_REQUESTED",
                    message="Cancellation requested; menunggu safe checkpoint.",
                )

    def _gate(self, job_id: str) -> HRISInteractionGate:
        gate = self._gates.get(job_id)
        if gate is None:
            raise RuntimeError("HRIS job tidak sedang menunggu konfirmasi.")
        return gate

    @staticmethod
    def _unified_status(state: HRISJobState) -> str:
        if state == HRISJobState.VALIDATING:
            return "VALIDATING"
        if state == HRISJobState.READY:
            return "READY_FOR_UPLOAD"
        if state in {
            HRISJobState.WAITING_FOR_LOGIN,
            HRISJobState.WAITING_FOR_USER_UPLOAD,
            HRISJobState.WAITING_FOR_CHECKPOINT,
            HRISJobState.WAITING_FOR_VERIFICATION,
            HRISJobState.PAUSED,
        }:
            return "PAUSED"
        return "RUNNING"

    @staticmethod
    def _source_summary(resolved, result=None) -> str:
        return json.dumps(
            {
                "source_folder": str(resolved.source_folder),
                "recorder_profile": str(resolved.recorder_profile),
                "configuration": str(resolved.configuration_path or "OAS-K Database"),
                "manual_upload": False,
                "result": result.error_summary if result else None,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _record_result_files(repository, job_pk, result) -> None:
        values = (
            ("PROCESS_LOG", result.process_log_path),
            ("UPLOAD_REPORT", result.report_path),
            ("UPLOAD_SUMMARY_JSON", result.summary_json_path),
            ("OUTPUT_FOLDER", result.output_folder),
        )
        for role, path in values:
            if path and path.exists():
                repository.add_job_file(
                    JobFileRecord(
                        job_pk,
                        role,
                        str(path),
                        result.ended_at,
                        file_size=path.stat().st_size if path.is_file() else None,
                        last_checked_at=result.ended_at,
                    )
                )
        for item in result.files:
            if item.uploaded_path and item.uploaded_path.exists():
                repository.add_job_file(
                    JobFileRecord(
                        job_pk,
                        "UPLOADED_TXT",
                        str(item.uploaded_path),
                        result.ended_at,
                        file_size=item.uploaded_path.stat().st_size,
                        last_checked_at=result.ended_at,
                    )
                )

    @staticmethod
    def _validate_period(start: str | None, end: str | None) -> None:
        if not start or not end:
            raise ValueError("Start Date dan End Date wajib diisi.")
        try:
            start_value, end_value = date.fromisoformat(start), date.fromisoformat(end)
        except ValueError as exc:
            raise ValueError("Tanggal HRIS harus memakai format YYYY-MM-DD.") from exc
        if start_value > end_value:
            raise ValueError("Start Date tidak boleh setelah End Date.")

    @staticmethod
    def _validate_output_parent(path: Path) -> None:
        candidate = path
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if not candidate.is_dir() or not os.access(candidate, os.W_OK):
            raise ValueError("Output Root tidak memiliki parent writable.")

    @staticmethod
    def _new_job_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"UI-HRIS-{stamp}-{uuid.uuid4().hex[:6].upper()}"
