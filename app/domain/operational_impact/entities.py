from dataclasses import dataclass, field, replace
from datetime import date, datetime
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4

from app.domain.operational_impact.rules import (
    require_items,
    require_text,
    validate_score,
)
from app.domain.operational_impact.value_objects import (
    ImpactDirection,
    ImpactGovernanceStatus,
    ImpactLevel,
    PriorityLevel,
)
from app.models.kpi import utc_now


@dataclass(frozen=True)
class OperationalImpactDefinition:
    impact_definition_id: str
    tenant_id: str
    name: str
    description: str
    impact_category: str
    owner: str
    steward: str
    status: ImpactGovernanceStatus
    impact_definition_version: str
    effective_date: date
    created_by: str
    updated_by: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    approved_by: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self):
        for name in (
            "impact_definition_id",
            "tenant_id",
            "name",
            "impact_category",
            "owner",
            "steward",
            "impact_definition_version",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self,
            "status",
            ImpactGovernanceStatus.from_value(self.status),
        )

    def approve(self, approver):
        approver = require_text(approver, "approver")
        if approver == self.created_by:
            raise PermissionError("Creator cannot approve own definition.")
        now = utc_now()
        return replace(
            self,
            status=ImpactGovernanceStatus.APPROVED,
            approved_by=approver,
            approved_at=now,
            updated_by=approver,
            updated_at=now,
        )

    def activate(self, actor):
        if self.status != ImpactGovernanceStatus.APPROVED:
            raise ValueError("Only approved definitions can be activated.")
        return replace(
            self,
            status=ImpactGovernanceStatus.ACTIVE,
            updated_by=require_text(actor, "updated_by"),
            updated_at=utc_now(),
        )


@dataclass(frozen=True)
class OperationalImpactFactor:
    impact_factor_id: str
    tenant_id: str
    impact_definition_id: str
    impact_definition_version: str
    name: str
    description: str
    source_reference: str
    weight: float
    direction: ImpactDirection
    threshold_version: str
    threshold_min: float
    threshold_max: float
    impact_factor_version: str
    owner: str
    steward: str
    status: ImpactGovernanceStatus
    effective_date: date
    created_by: str
    updated_by: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    approved_by: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self):
        for name in (
            "impact_factor_id",
            "tenant_id",
            "impact_definition_id",
            "impact_definition_version",
            "name",
            "source_reference",
            "threshold_version",
            "impact_factor_version",
            "owner",
            "steward",
            "created_by",
            "updated_by",
        ):
            require_text(getattr(self, name), name)
        if not 0 < float(self.weight) <= 1:
            raise ValueError("weight must be greater than 0 and at most 1.")
        if float(self.threshold_min) >= float(self.threshold_max):
            raise ValueError("threshold_min must be less than threshold_max.")
        if not self.source_reference.startswith(("kpi:", "risk:")):
            raise ValueError(
                "source_reference must use a governed kpi: or risk: reference."
            )
        object.__setattr__(self, "weight", float(self.weight))
        object.__setattr__(
            self,
            "direction",
            ImpactDirection.from_value(self.direction),
        )
        object.__setattr__(
            self,
            "status",
            ImpactGovernanceStatus.from_value(self.status),
        )

    def approve(self, approver):
        approver = require_text(approver, "approver")
        if approver == self.created_by:
            raise PermissionError("Creator cannot approve own factor.")
        now = utc_now()
        return replace(
            self,
            status=ImpactGovernanceStatus.APPROVED,
            approved_by=approver,
            approved_at=now,
            updated_by=approver,
            updated_at=now,
        )

    def activate(self, actor):
        if self.status != ImpactGovernanceStatus.APPROVED:
            raise ValueError("Only approved factors can be activated.")
        return replace(
            self,
            status=ImpactGovernanceStatus.ACTIVE,
            updated_by=require_text(actor, "updated_by"),
            updated_at=utc_now(),
        )


@dataclass(frozen=True)
class OperationalImpactAssessmentRequest:
    impact_definition_id: str
    entity_type: str
    entity_id: str
    assessment_period_start: datetime
    assessment_period_end: datetime
    source_kpi_result_ids: tuple[str, ...] = ()
    source_risk_result_ids: tuple[str, ...] = ()

    def __post_init__(self):
        require_text(self.impact_definition_id, "impact_definition_id")
        require_text(self.entity_type, "entity_type")
        require_text(self.entity_id, "entity_id")
        if self.assessment_period_start > self.assessment_period_end:
            raise ValueError(
                "assessment_period_start must be before or equal to "
                "assessment_period_end."
            )
        if not self.source_kpi_result_ids and not self.source_risk_result_ids:
            raise ValueError("Governed KPI or Risk Result reference is required.")


@dataclass(frozen=True)
class OperationalImpactAssessment:
    impact_assessment_id: str
    tenant_id: str
    impact_definition_id: str
    entity_type: str
    entity_id: str
    assessment_period_start: datetime
    assessment_period_end: datetime
    impact_score: float
    impact_level: ImpactLevel
    impact_definition_version: str
    impact_factor_ids: tuple[str, ...]
    impact_factor_versions: Mapping[str, str]
    threshold_versions: Mapping[str, str]
    weight_snapshots: Mapping[str, float]
    factor_score_snapshots: Mapping[str, float]
    source_kpi_result_ids: tuple[str, ...]
    source_risk_result_ids: tuple[str, ...]
    lineage_id: str
    created_by: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in (
            "impact_assessment_id",
            "tenant_id",
            "impact_definition_id",
            "entity_type",
            "entity_id",
            "impact_definition_version",
            "lineage_id",
            "created_by",
        ):
            require_text(getattr(self, name), name)
        require_items(self.impact_factor_ids, "impact_factor_ids")
        require_items(self.impact_factor_versions, "impact_factor_versions")
        require_items(self.threshold_versions, "threshold_versions")
        object.__setattr__(
            self,
            "impact_score",
            validate_score(self.impact_score, "impact_score"),
        )
        object.__setattr__(
            self,
            "impact_level",
            ImpactLevel.from_value(self.impact_level),
        )
        for name in (
            "impact_factor_versions",
            "threshold_versions",
            "weight_snapshots",
            "factor_score_snapshots",
        ):
            object.__setattr__(
                self,
                name,
                MappingProxyType(dict(getattr(self, name))),
            )


@dataclass(frozen=True)
class RiskPriorityAssessment:
    priority_assessment_id: str
    tenant_id: str
    risk_result_id: str
    risk_definition_version: str
    risk_rule_version: str
    impact_assessment_id: str
    impact_definition_version: str
    entity_type: str
    entity_id: str
    risk_score_snapshot: float
    impact_score_snapshot: float
    priority_score: float
    priority_level: PriorityLevel
    priority_reason: str
    lineage_id: str
    created_by: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in (
            "priority_assessment_id",
            "tenant_id",
            "risk_result_id",
            "risk_definition_version",
            "risk_rule_version",
            "impact_assessment_id",
            "impact_definition_version",
            "entity_type",
            "entity_id",
            "priority_reason",
            "lineage_id",
            "created_by",
        ):
            require_text(getattr(self, name), name)
        for name in (
            "risk_score_snapshot",
            "impact_score_snapshot",
            "priority_score",
        ):
            object.__setattr__(
                self,
                name,
                validate_score(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "priority_level",
            PriorityLevel.from_value(self.priority_level),
        )


@dataclass(frozen=True)
class OperationalImpactTimelineEvent:
    timeline_event_id: str
    tenant_id: str
    employee_id: str
    impact_assessment_id: str
    priority_assessment_id: str
    event_type: str
    material_change_reason: str
    impact_level_snapshot: ImpactLevel
    priority_level_snapshot: PriorityLevel
    created_by: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        for name in (
            "timeline_event_id",
            "tenant_id",
            "employee_id",
            "impact_assessment_id",
            "priority_assessment_id",
            "event_type",
            "material_change_reason",
            "created_by",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self,
            "impact_level_snapshot",
            ImpactLevel.from_value(self.impact_level_snapshot),
        )
        object.__setattr__(
            self,
            "priority_level_snapshot",
            PriorityLevel.from_value(self.priority_level_snapshot),
        )


def new_id():
    return str(uuid4())
