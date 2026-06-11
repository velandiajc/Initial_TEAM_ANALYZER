from dataclasses import dataclass, field, replace
from datetime import datetime

from app.domain.performance.rules.coaching_lineage_rules import (
    require_lineage_id,
    require_text,
)
from app.domain.performance.rules.followup_rules import validate_followup_transition
from app.domain.performance.value_objects import FollowUpStatus
from app.models.kpi import utc_now


@dataclass(frozen=True)
class CoachingFollowUp:
    followup_id: str
    tenant_id: str
    session_id: str
    commitment_id: str
    reviewer_id: str
    outcome: str
    lineage_id: str
    created_by: str
    updated_by: str
    status: FollowUpStatus = FollowUpStatus.SCHEDULED
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "followup_id",
            "tenant_id",
            "session_id",
            "commitment_id",
            "reviewer_id",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, field_name), field_name)
        require_lineage_id(self.lineage_id)
        object.__setattr__(self, "outcome", str(self.outcome).strip())
        object.__setattr__(
            self,
            "status",
            FollowUpStatus.from_value(self.status),
        )
        if self.status != FollowUpStatus.SCHEDULED:
            require_text(self.outcome, "outcome")

    def with_status(
        self,
        status: FollowUpStatus | str,
        outcome: str,
        updated_by: str,
        updated_at: datetime | None = None,
    ) -> "CoachingFollowUp":
        status = FollowUpStatus.from_value(status)
        validate_followup_transition(self.status, status)
        return replace(
            self,
            status=status,
            outcome=require_text(outcome, "outcome"),
            updated_by=require_text(updated_by, "updated_by"),
            updated_at=updated_at or utc_now(),
        )
