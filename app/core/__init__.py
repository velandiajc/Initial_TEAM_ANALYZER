from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    """
    Generic performance entity.

    This can represent:
    - Agent
    - Supervisor
    - QA Analyst
    - Trainer
    - Team
    - Campaign
    """

    entity_id: str
    name: str
    entity_type: str
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status.lower() == "active"

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)