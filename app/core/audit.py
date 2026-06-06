from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.models.kpi import utc_now


@dataclass
class AuditEvent:
    action: str
    tenant_id: str
    actor_user_id: str
    entity_type: str
    entity_id: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.event_id, "event_id")
        _require_text(self.action, "action")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.actor_user_id, "actor_user_id")
        _require_text(self.entity_type, "entity_type")
        _require_text(self.entity_id, "entity_id")


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")
