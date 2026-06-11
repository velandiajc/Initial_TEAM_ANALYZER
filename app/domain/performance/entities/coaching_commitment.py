from dataclasses import dataclass, field, replace
from datetime import date, datetime

from app.domain.performance.rules.coaching_lineage_rules import (
    require_lineage_id,
    require_text,
)
from app.domain.performance.rules.commitment_rules import (
    validate_commitment_transition,
)
from app.domain.performance.value_objects import CommitmentStatus
from app.models.kpi import utc_now


@dataclass(frozen=True)
class CoachingCommitment:
    commitment_id: str
    tenant_id: str
    session_id: str
    employee_id: str
    description: str
    target_date: date
    lineage_id: str
    created_by: str
    updated_by: str
    status: CommitmentStatus = CommitmentStatus.OPEN
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "commitment_id",
            "tenant_id",
            "session_id",
            "employee_id",
            "description",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, field_name), field_name)
        require_lineage_id(self.lineage_id)
        if not isinstance(self.target_date, date):
            raise ValueError("target_date is required.")
        object.__setattr__(
            self,
            "status",
            CommitmentStatus.from_value(self.status),
        )

    def with_status(
        self,
        status: CommitmentStatus | str,
        updated_by: str,
        updated_at: datetime | None = None,
    ) -> "CoachingCommitment":
        status = CommitmentStatus.from_value(status)
        validate_commitment_transition(self.status, status)
        return replace(
            self,
            status=status,
            updated_by=require_text(updated_by, "updated_by"),
            updated_at=updated_at or utc_now(),
        )
