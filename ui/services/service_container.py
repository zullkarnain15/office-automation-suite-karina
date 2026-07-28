"""Explicit non-global dependency container for Settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AppServices:
    storage_service: Any
    database_service: Any
    configuration_service: Any
    recovery_service: Any
    recorder_profile_service: Any
    task_runner: Any
    dialog_service: Any
    file_system_service: Any
    dashboard_service: Any = None
    history_service: Any = None
    system_health_service: Any = None
    attendance_service: Any = None
    outlook_revisi_service: Any = None
    module_configuration_service: Any = None
    hris_service: Any = None
    utilities_service: Any = None
    comparison_result_service: Any = None
    attachment_consolidation_service: Any = None


def build_default_app_services(
    root: Any,
    *,
    application_version: str,
    project_root: Path,
    registry: Any | None = None,
    default_data_root: Path | None = None,
) -> AppServices:
    from shared.storage.registry import (
        StorageRegistryService,
        WindowsRegistryBackend,
    )
    from ui.services.configuration_ui_service import ConfigurationUIService
    from ui.adapters.attendance_adapter import AttendanceAdapter
    from ui.adapters.outlook_revisi_adapter import OutlookRevisiAdapter
    from ui.adapters.hris_adapter import HRISAdapter
    from ui.adapters.attachment_consolidation_adapter import (
        AttachmentConsolidationAdapter,
    )
    from ui.adapters.comparison_result_adapter import ComparisonResultAdapter
    from ui.services.attendance_service import AttendanceService
    from ui.services.database_settings_service import DatabaseSettingsService
    from ui.services.dashboard_service import DashboardService
    from ui.services.dialog_service import TkDialogService
    from ui.services.filesystem_service import FileSystemService
    from ui.services.history_service import HistoryService
    from ui.services.hris_service import HRISService
    from ui.services.attachment_consolidation_service import (
        AttachmentConsolidationService,
    )
    from ui.services.comparison_result_service import ComparisonResultService
    from ui.services.utilities_service import UtilitiesService
    from ui.services.outlook_revisi_service import OutlookRevisiService
    from ui.services.module_configuration_service import ModuleConfigurationService
    from ui.services.recorder_profile_ui_service import (
        RecorderProfileUIService,
    )
    from ui.services.recovery_ui_service import RecoveryUIService
    from ui.services.storage_ui_service import StorageUIService
    from ui.services.system_health_service import SystemHealthService
    from ui.services.task_runner import TaskRunner

    registry = registry or StorageRegistryService(WindowsRegistryBackend())
    storage_arguments = {}
    if default_data_root is not None:
        storage_arguments["default_data_root"] = default_data_root
    storage_service = StorageUIService(
        registry,
        application_version=application_version,
        **storage_arguments,
    )
    return AppServices(
        storage_service=storage_service,
        database_service=DatabaseSettingsService(),
        configuration_service=ConfigurationUIService(
            project_root / "config" / "templates" / "OAS-K_Configuration_Template.xlsx"
        ),
        recovery_service=RecoveryUIService(
            registry,
            application_version=application_version,
        ),
        recorder_profile_service=RecorderProfileUIService(),
        task_runner=TaskRunner(root.after),
        dialog_service=TkDialogService(root),
        file_system_service=FileSystemService(),
        dashboard_service=DashboardService(storage_service),
        history_service=HistoryService(storage_service),
        system_health_service=SystemHealthService(storage_service),
        attendance_service=AttendanceService(storage_service, AttendanceAdapter()),
        outlook_revisi_service=OutlookRevisiService(
            storage_service, OutlookRevisiAdapter()
        ),
        module_configuration_service=ModuleConfigurationService(),
        hris_service=HRISService(storage_service, HRISAdapter()),
        utilities_service=UtilitiesService(storage_service),
        comparison_result_service=ComparisonResultService(
            storage_service, ComparisonResultAdapter()
        ),
        attachment_consolidation_service=AttachmentConsolidationService(
            storage_service, AttachmentConsolidationAdapter()
        ),
    )
