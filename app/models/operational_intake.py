from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.models.kpi import utc_now


@dataclass
class OperationalIntakeRecord:
    tenant_id: str
    run_id: str
    contact_id: str
    score: float
    classification: str
    driver: str
    impact_score: float
    sub_driver: str = ""
    csat_category: str = ""
    agent_id: str = ""
    agent_name: str = ""
    survey_date: str = ""
    brand: str = ""
    media_type: str = ""
    disposition: str = ""
    intake_record_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.run_id, "run_id")
        _require_text(self.intake_record_id, "intake_record_id")
        _require_text(self.contact_id, "contact_id")
        _require_text(self.classification, "classification")
        _require_text(self.driver, "driver")
        self.score = float(self.score)
        self.impact_score = float(self.impact_score)


@dataclass
class OperationalIntakePriority:
    tenant_id: str
    run_id: str
    driver: str
    detractor_count: int
    impact_score: float
    impact_rank: int
    priority_rank: int
    priority_reason: str
    priority_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.run_id, "run_id")
        _require_text(self.priority_id, "priority_id")
        _require_text(self.driver, "driver")
        _require_text(self.priority_reason, "priority_reason")
        self.detractor_count = int(self.detractor_count)
        self.impact_score = float(self.impact_score)
        self.impact_rank = int(self.impact_rank)
        self.priority_rank = int(self.priority_rank)


@dataclass
class OperationalIntakeRun:
    tenant_id: str
    source_file: str
    source_file_name: str
    total_records: int
    detractor_count: int
    created_by: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    records: list[OperationalIntakeRecord] = field(default_factory=list)
    priorities: list[OperationalIntakePriority] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.run_id, "run_id")
        _require_text(self.source_file, "source_file")
        _require_text(self.source_file_name, "source_file_name")
        _require_text(self.created_by, "created_by")
        self.total_records = int(self.total_records)
        self.detractor_count = int(self.detractor_count)


@dataclass
class OperationalIntakeReport:
    tenant_id: str
    run_id: str
    report_path: str
    content: str
    report_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.run_id, "run_id")
        _require_text(self.report_id, "report_id")
        _require_text(self.report_path, "report_path")
        _require_text(self.content, "content")


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")
