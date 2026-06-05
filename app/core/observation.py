from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast


@dataclass
class Observation:
    """
    Generic performance observation.

    This can represent:
    - Survey result
    - QA score
    - Attendance event
    - Adherence event
    - Call metadata
    - Transcript insight
    - Coaching session
    """

    observation_id: str
    entity_id: str
    source_type: str
    observed_at: datetime | None = None
    score: float | None = None
    category: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=lambda: cast(
            dict[str, Any],
            {}
        )
    )

    def has_score(self) -> bool:
        return self.score is not None

    def get_metadata(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        return self.metadata.get(
            key,
            default
        )

    def normalized_source_type(self) -> str:
        return self.source_type.strip().lower()