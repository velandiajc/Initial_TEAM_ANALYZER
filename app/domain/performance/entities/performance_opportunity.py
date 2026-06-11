from dataclasses import dataclass, field, replace
from datetime import datetime

from app.domain.performance.rules.coaching_lineage_rules import (
    require_lineage_id,
    require_text,
)
from app.domain.performance.rules.performance_opportunity_rules import (
    validate_opportunity_transition,
)
from app.domain.performance.value_objects import PerformanceOpportunityStatus
from app.models.kpi import utc_now


@dataclass(frozen=True)
class PerformanceOpportunity:
    opportunity_id: str
    tenant_id: str
    employee_id: str
    opportunity_type: str
    business_reason: str
    evidence_pack_id: str
    risk_result_id: str
    owner: str
    lineage_id: str
    created_by: str
    updated_by: str
    status: PerformanceOpportunityStatus = (
        PerformanceOpportunityStatus.IDENTIFIED
    )
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "opportunity_id",
            "tenant_id",
            "employee_id",
            "opportunity_type",
            "business_reason",
            "evidence_pack_id",
            "risk_result_id",
            "owner",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, field_name), field_name)
        require_lineage_id(self.lineage_id)
        object.__setattr__(
            self,
            "status",
            PerformanceOpportunityStatus.from_value(self.status),
        )

    def with_status(
        self,
        status: PerformanceOpportunityStatus | str,
        updated_by: str,
        updated_at: datetime | None = None,
    ) -> "PerformanceOpportunity":
        status = PerformanceOpportunityStatus.from_value(status)
        validate_opportunity_transition(self.status, status)
        return replace(
            self,
            status=status,
            updated_by=require_text(updated_by, "updated_by"),
            updated_at=updated_at or utc_now(),
        )
