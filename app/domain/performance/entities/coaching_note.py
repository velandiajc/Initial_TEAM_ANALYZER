from dataclasses import dataclass, field
from datetime import datetime

from app.domain.performance.rules.coaching_lineage_rules import (
    require_lineage_id,
    require_text,
)
from app.domain.performance.value_objects import CoachingNoteVisibility
from app.models.kpi import utc_now


@dataclass(frozen=True)
class CoachingNote:
    note_id: str
    tenant_id: str
    session_id: str
    visibility_level: CoachingNoteVisibility
    content_reference: str
    lineage_id: str
    created_by: str
    updated_by: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        for field_name in (
            "note_id",
            "tenant_id",
            "session_id",
            "content_reference",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, field_name), field_name)
        require_lineage_id(self.lineage_id)
        object.__setattr__(
            self,
            "visibility_level",
            CoachingNoteVisibility.from_value(self.visibility_level),
        )
