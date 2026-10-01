"""Side-effect-free recovery state and recommendation service."""

from __future__ import annotations

from shared.database.constants import SCHEMA_VERSION
from shared.recovery.constants import RecoveryAction, RecoveryStatus
from shared.recovery.models import (
    CandidateValidationResult,
    RecoveryRecommendation,
    RecoveryState,
)
from shared.storage.models import StartupStorageResolution, StartupStorageStatus


class RecoveryService:
    """Describe recovery choices without executing any recovery action."""

    def assess(
        self,
        startup: StartupStorageResolution,
        database: CandidateValidationResult | None,
        *,
        backups_available: bool,
        registry_pointer_valid: bool = True,
    ) -> RecoveryState:
        statuses: list[RecoveryStatus] = []
        diagnostics: list[str] = [*startup.warnings, *startup.errors]

        if startup.status == StartupStorageStatus.INVALID_LOCATION:
            statuses.append(RecoveryStatus.DATA_ROOT_UNAVAILABLE)
        if (
            not registry_pointer_valid
            or startup.status == StartupStorageStatus.REGISTRY_UNAVAILABLE
        ):
            statuses.append(RecoveryStatus.REGISTRY_POINTER_INVALID)
        if database is None or not database.exists:
            statuses.append(RecoveryStatus.DATABASE_MISSING)
        elif database.schema_version not in {None, SCHEMA_VERSION}:
            statuses.append(RecoveryStatus.SCHEMA_INCOMPATIBLE)
        elif not database.can_activate:
            statuses.append(RecoveryStatus.DATABASE_INVALID)

        if statuses:
            statuses.append(
                RecoveryStatus.BACKUP_AVAILABLE
                if backups_available
                else RecoveryStatus.NO_BACKUP_AVAILABLE
            )
        else:
            statuses.append(RecoveryStatus.HEALTHY)

        recommendations = self._recommend(statuses, backups_available)
        return RecoveryState(
            primary_status=statuses[0],
            statuses=tuple(statuses),
            recommendations=recommendations,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _recommend(
        statuses: list[RecoveryStatus],
        backups_available: bool,
    ) -> tuple[RecoveryRecommendation, ...]:
        if statuses == [RecoveryStatus.HEALTHY]:
            return (
                RecoveryRecommendation(
                    RecoveryAction.CANCEL,
                    "The active database is healthy; recovery is unnecessary.",
                    1,
                ),
            )
        recommendations: list[RecoveryRecommendation] = []
        if RecoveryStatus.DATA_ROOT_UNAVAILABLE in statuses:
            recommendations.append(
                RecoveryRecommendation(
                    RecoveryAction.SELECT_DATA_ROOT,
                    "Select an available local Data Root.",
                    1,
                )
            )
        if backups_available:
            recommendations.extend(
                (
                    RecoveryRecommendation(
                        RecoveryAction.RESTORE_LAST_BACKUP,
                        "A validated backup may restore service fastest.",
                        2,
                    ),
                    RecoveryRecommendation(
                        RecoveryAction.SELECT_BACKUP,
                        "Select another official backup.",
                        3,
                    ),
                )
            )
        recommendations.extend(
            (
                RecoveryRecommendation(
                    RecoveryAction.IMPORT_EXISTING_DATABASE,
                    "Import a compatible database into the active Data Root.",
                    4,
                ),
                RecoveryRecommendation(
                    RecoveryAction.RESET_TO_DEFAULT,
                    "Create a new empty schema-v1 database after confirmation.",
                    5,
                ),
                RecoveryRecommendation(
                    RecoveryAction.OPEN_DIAGNOSTICS,
                    "Review validation details before choosing an operation.",
                    6,
                ),
                RecoveryRecommendation(
                    RecoveryAction.CANCEL,
                    "Leave recovery without changing storage.",
                    7,
                ),
            )
        )
        return tuple(recommendations)


def assess_recovery(
    startup: StartupStorageResolution,
    database: CandidateValidationResult | None,
    *,
    backups_available: bool,
    registry_pointer_valid: bool = True,
) -> RecoveryState:
    return RecoveryService().assess(
        startup,
        database,
        backups_available=backups_available,
        registry_pointer_valid=registry_pointer_valid,
    )
