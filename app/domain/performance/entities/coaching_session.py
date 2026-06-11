from dataclasses import dataclass, field, replace
from datetime import datetime

from app.domain.performance.rules.coaching_lineage_rules import (
    require_lineage_id,
    require_text,
)
from app.domain.performance.rules.coaching_session_rules import (
    validate_session_transition,
)
from app.domain.performance.value_objects import CoachingSessionStatus
from app.models.kpi import utc_now


@dataclass(frozen=True)
class CoachingSession:
    coaching_session_id: str
    tenant_id: str
    employee_id: str
    session_owner_id: str
    performance_opportunity_id: str
    evidence_pack_id: str
    evidence_version_snapshot: str
    evidence_artifact_ids_snapshot: tuple[str, ...]
    risk_result_id: str
    risk_score_snapshot: float
    risk_level_snapshot: str
    risk_classification_snapshot: str
    risk_definition_version: str
    risk_rule_version: str
    coaching_version: str
    lineage_id: str
    created_by: str
    updated_by: str
    status: CoachingSessionStatus = CoachingSessionStatus.DRAFT
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "coaching_session_id",
            "tenant_id",
            "employee_id",
            "session_owner_id",
            "performance_opportunity_id",
            "evidence_pack_id",
            "evidence_version_snapshot",
            "risk_result_id",
            "risk_level_snapshot",
            "risk_classification_snapshot",
            "risk_definition_version",
            "risk_rule_version",
            "coaching_version",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, field_name), field_name)
        require_lineage_id(self.lineage_id)
        object.__setattr__(
            self,
            "evidence_artifact_ids_snapshot",
            tuple(
                require_text(item, "evidence_artifact_id")
                for item in self.evidence_artifact_ids_snapshot
            ),
        )
        object.__setattr__(
            self,
            "risk_score_snapshot",
            float(self.risk_score_snapshot),
        )
        object.__setattr__(
            self,
            "status",
            CoachingSessionStatus.from_value(self.status),
        )

    def with_status(
        self,
        status: CoachingSessionStatus | str,
        updated_by: str,
        updated_at: datetime | None = None,
    ) -> "CoachingSession":
        status = CoachingSessionStatus.from_value(status)
        validate_session_transition(self.status, status)
        return replace(
            self,
            status=status,
            updated_by=require_text(updated_by, "updated_by"),
            updated_at=updated_at or utc_now(),
        )
