"""Excel template and configuration export API for DB2B."""

from shared.database.exporting.current_config_exporter import (
    export_current_configuration,
)
from shared.database.exporting.exceptions import (
    ConfigExportError,
    LegacyExportUnsupportedError,
    WorkbookValidationError,
)
from shared.database.exporting.models import (
    ExportResult,
    WorkbookValidationResult,
)
from shared.database.exporting.legacy_exporter import (
    export_attendance_legacy,
    export_hris_legacy,
    export_outlook_legacy,
)
from shared.database.exporting.template_builder import (
    build_configuration_template,
)
from shared.database.exporting.workbook_validator import (
    validate_configuration_workbook,
)

__all__ = [
    "ConfigExportError",
    "ExportResult",
    "LegacyExportUnsupportedError",
    "WorkbookValidationError",
    "WorkbookValidationResult",
    "build_configuration_template",
    "export_attendance_legacy",
    "export_current_configuration",
    "export_hris_legacy",
    "export_outlook_legacy",
    "validate_configuration_workbook",
]
