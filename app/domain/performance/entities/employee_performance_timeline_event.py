from dataclasses import dataclass, field
from datetime import datetime

from app.domain.performance.rules.coaching_lineage_rules import require_text
from app.domain.performance.rules.timeline_rules import validate_timeline_reference
from app.domain.performance.value_objects import PerformanceTimelineEventSource
from app.models.kpi import utc_now


@dataclass(frozen=True)
class EmployeePerformanceTimelineEvent:
    timeline_event_id: str
    tenant_id: str
    employee_id: str
    event_type: str
    event_source: PerformanceTimelineEventSource
    source_entity_id: str
    lineage_id: str
    created_by: str
    updated_by: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "timeline_event_id",
            "tenant_id",
            "event_type",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, field_name), field_name)
        validate_timeline_reference(
            self.employee_id,
            self.source_entity_id,
            self.lineage_id,
        )
        object.__setattr__(
            self,
            "event_source",
            PerformanceTimelineEventSource.from_value(self.event_source),
        )
