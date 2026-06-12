from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from app.models.kpi import utc_now


def _text(value, field_name):
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def _lineage(values):
    items = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )
    if not items:
        raise ValueError("lineage_references are required.")
    return items


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze(item)
            for key, item in value.items()
        })
    if isinstance(value, (list, tuple, set)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class SupervisorPriorityQueueItem:
    tenant_id: str
    employee_id: str
    employee_display_name: str
    priority_level: str
    priority_score: float
    risk_score: float
    impact_score: float
    risk_drivers: tuple[str, ...]
    impact_drivers: tuple[str, ...]
    priority_reason: str
    recommended_action_type: str
    last_coaching_date: datetime | None
    open_commitments_count: int
    lineage_id: str
    lineage_references: tuple[str, ...]

    def __post_init__(self):
        for name in (
            "tenant_id",
            "employee_id",
            "employee_display_name",
            "priority_level",
            "priority_reason",
            "recommended_action_type",
            "lineage_id",
        ):
            _text(getattr(self, name), name)
        for name in ("priority_score", "risk_score", "impact_score"):
            object.__setattr__(self, name, float(getattr(self, name)))
        object.__setattr__(self, "risk_drivers", tuple(self.risk_drivers))
        object.__setattr__(self, "impact_drivers", tuple(self.impact_drivers))
        object.__setattr__(
            self,
            "open_commitments_count",
            int(self.open_commitments_count),
        )
        object.__setattr__(
            self,
            "lineage_references",
            _lineage(self.lineage_references),
        )


@dataclass(frozen=True)
class SupervisorCommandCenterView:
    tenant_id: str
    supervisor_id: str
    priority_queue: tuple[SupervisorPriorityQueueItem, ...]
    team_health_summary: Mapping[str, Any]
    immediate_intervention_count: int
    escalate_count: int
    coach_count: int
    monitor_count: int
    top_operational_impact_drivers: tuple[str, ...]
    open_commitments_count: int
    overdue_followups_count: int
    lineage_references: tuple[str, ...]
    generated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        _text(self.tenant_id, "tenant_id")
        _text(self.supervisor_id, "supervisor_id")
        object.__setattr__(self, "priority_queue", tuple(self.priority_queue))
        object.__setattr__(
            self,
            "team_health_summary",
            _freeze(self.team_health_summary),
        )
        object.__setattr__(
            self,
            "top_operational_impact_drivers",
            tuple(self.top_operational_impact_drivers),
        )
        object.__setattr__(
            self,
            "lineage_references",
            _lineage(self.lineage_references),
        )


@dataclass(frozen=True)
class TeamPerformanceView:
    tenant_id: str
    team_id: str
    supervisor_id: str
    employees: tuple[Mapping[str, Any], ...]
    risk_distribution: Mapping[str, int]
    impact_distribution: Mapping[str, int]
    priority_distribution: Mapping[str, int]
    team_kpi_summary: tuple[Mapping[str, Any], ...]
    team_coaching_summary: Mapping[str, Any]
    lineage_references: tuple[str, ...]
    generated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in ("tenant_id", "team_id", "supervisor_id"):
            _text(getattr(self, name), name)
        for name in (
            "employees",
            "team_kpi_summary",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        for name in (
            "risk_distribution",
            "impact_distribution",
            "priority_distribution",
            "team_coaching_summary",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        object.__setattr__(
            self,
            "lineage_references",
            _lineage(self.lineage_references),
        )


@dataclass(frozen=True)
class AgentPerformanceProfileView:
    tenant_id: str
    employee_id: str
    employee_display_name: str
    risk_summary: Mapping[str, Any]
    impact_summary: Mapping[str, Any]
    priority_summary: Mapping[str, Any]
    kpi_summary: tuple[Mapping[str, Any], ...]
    evidence_references: tuple[str, ...]
    coaching_summary: Mapping[str, Any]
    open_commitments: tuple[Mapping[str, Any], ...]
    timeline_preview: tuple[Mapping[str, Any], ...]
    lineage_references: tuple[str, ...]

    def __post_init__(self):
        for name in ("tenant_id", "employee_id", "employee_display_name"):
            _text(getattr(self, name), name)
        for name in (
            "risk_summary",
            "impact_summary",
            "priority_summary",
            "coaching_summary",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        for name in (
            "kpi_summary",
            "open_commitments",
            "timeline_preview",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        object.__setattr__(
            self,
            "evidence_references",
            tuple(self.evidence_references),
        )
        object.__setattr__(
            self,
            "lineage_references",
            _lineage(self.lineage_references),
        )


@dataclass(frozen=True)
class EmployeePerformanceTimelineView:
    tenant_id: str
    employee_id: str
    events: tuple[Mapping[str, Any], ...]
    event_count: int
    date_range_start: datetime | None
    date_range_end: datetime | None
    lineage_references: tuple[str, ...]

    def __post_init__(self):
        _text(self.tenant_id, "tenant_id")
        _text(self.employee_id, "employee_id")
        object.__setattr__(self, "events", _freeze(self.events))
        object.__setattr__(self, "event_count", len(self.events))
        object.__setattr__(
            self,
            "lineage_references",
            _lineage(self.lineage_references),
        )


@dataclass(frozen=True)
class CoachingWorkspaceView:
    tenant_id: str
    employee_id: str
    coaching_context: Mapping[str, Any]
    linked_priority_assessment: Mapping[str, Any]
    linked_impact_assessment: Mapping[str, Any]
    linked_evidence_references: tuple[str, ...]
    opportunities: tuple[Mapping[str, Any], ...]
    commitments: tuple[Mapping[str, Any], ...]
    followups: tuple[Mapping[str, Any], ...]
    private_note_access: bool
    lineage_references: tuple[str, ...]

    def __post_init__(self):
        _text(self.tenant_id, "tenant_id")
        _text(self.employee_id, "employee_id")
        for name in (
            "coaching_context",
            "linked_priority_assessment",
            "linked_impact_assessment",
            "opportunities",
            "commitments",
            "followups",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        object.__setattr__(
            self,
            "linked_evidence_references",
            tuple(self.linked_evidence_references),
        )
        object.__setattr__(
            self,
            "lineage_references",
            _lineage(self.lineage_references),
        )
