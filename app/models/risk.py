from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.kpi import utc_now
from app.models.kpi_calculation import KPICalculationResult


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_value(cls, value: "RiskLevel | str") -> "RiskLevel":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_")

        if normalized == "moderate":
            return cls.MEDIUM

        for level in cls:
            if level.value == normalized or level.name.lower() == normalized:
                return level

        raise ValueError(f"Unsupported risk level: {value}")


class RiskDefinitionLifecycle(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"

    @classmethod
    def from_value(
        cls,
        value: "RiskDefinitionLifecycle | str"
    ) -> "RiskDefinitionLifecycle":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_")
        legacy_values = {
            "pending_approval": "review",
            "archived": "deprecated",
        }
        normalized = legacy_values.get(normalized, normalized)

        for lifecycle in cls:
            if lifecycle.value == normalized or lifecycle.name.lower() == normalized:
                return lifecycle

        raise ValueError(f"Unsupported risk definition lifecycle: {value}")


class RiskRuleStatus(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"

    @classmethod
    def from_value(cls, value: "RiskRuleStatus | str") -> "RiskRuleStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_")
        legacy_values = {
            "pending_approval": "review",
            "rejected": "deprecated",
            "archived": "deprecated",
        }
        normalized = legacy_values.get(normalized, normalized)

        for status in cls:
            if status.value == normalized or status.name.lower() == normalized:
                return status

        raise ValueError(f"Unsupported risk rule status: {value}")


class RiskAssessmentStatus(Enum):
    SUCCESS = "success"
    MISSING_RULE = "missing_rule"
    RULE_CONFLICT = "rule_conflict"
    FAILED_VALIDATION = "failed_validation"
    REJECTED = "rejected"
    EXECUTION_ERROR = "execution_error"

    @classmethod
    def from_value(
        cls,
        value: "RiskAssessmentStatus | str"
    ) -> "RiskAssessmentStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_")

        for status in cls:
            if status.value == normalized or status.name.lower() == normalized:
                return status

        raise ValueError(f"Unsupported risk assessment status: {value}")


@dataclass
class RiskDefinition:
    risk_definition_id: str
    tenant_id: str
    name: str
    category: str
    owner_user_id: str
    steward_user_id: str
    lifecycle: RiskDefinitionLifecycle = RiskDefinitionLifecycle.DRAFT
    description: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_versions: list["RiskRuleVersion"] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.risk_definition_id, "risk_definition_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.name, "name")
        _require_text(self.category, "category")
        _require_text(self.owner_user_id, "owner_user_id")
        _require_text(self.steward_user_id, "steward_user_id")
        self.lifecycle = RiskDefinitionLifecycle.from_value(self.lifecycle)

    def move_to_lifecycle(
        self,
        lifecycle: RiskDefinitionLifecycle | str
    ) -> None:
        self.lifecycle = RiskDefinitionLifecycle.from_value(lifecycle)
        self.updated_at = utc_now()


@dataclass
class RiskRuleVersion:
    IMMUTABLE_AFTER_APPROVAL = {
        "tenant_id",
        "risk_definition_id",
        "version",
        "handler_key",
        "parameters",
        "created_by",
        "effective_from",
        "effective_to",
        "supersedes_rule_version_id",
    }

    rule_version_id: str
    tenant_id: str
    risk_definition_id: str
    version: str
    handler_key: str
    parameters: dict[str, Any]
    created_by: str
    status: RiskRuleStatus = RiskRuleStatus.REVIEW
    approved_by: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    approved_at: datetime | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    supersedes_rule_version_id: str | None = None
    is_active: bool = False
    notes: str = ""
    _approved_locked: bool = field(default=False, init=False, repr=False)

    def __setattr__(self, name, value) -> None:
        if (
            getattr(self, "_approved_locked", False)
            and name in self.IMMUTABLE_AFTER_APPROVAL
        ):
            raise AttributeError("Approved risk rules are immutable.")

        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        _require_text(self.rule_version_id, "rule_version_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.risk_definition_id, "risk_definition_id")
        _require_text(self.version, "version")
        _require_text(self.handler_key, "handler_key")
        _require_text(self.created_by, "created_by")
        self.status = RiskRuleStatus.from_value(self.status)
        self._validate_effective_period()

        if self.is_approved():
            object.__setattr__(self, "_approved_locked", True)

    def approve(
        self,
        approver_user_id: str,
        approved_at: datetime | None = None
    ) -> None:
        _require_text(approver_user_id, "approver_user_id")

        if approver_user_id == self.created_by:
            raise PermissionError("Creator cannot approve own risk rule.")

        object.__setattr__(self, "status", RiskRuleStatus.APPROVED)
        object.__setattr__(self, "approved_by", approver_user_id)
        object.__setattr__(self, "approved_at", approved_at or utc_now())
        object.__setattr__(self, "_approved_locked", True)

    def activate(self) -> None:
        if not self.is_approved():
            raise ValueError("Only approved risk rules can be activated.")

        object.__setattr__(self, "status", RiskRuleStatus.ACTIVE)
        object.__setattr__(self, "is_active", True)

    def deactivate(self) -> None:
        object.__setattr__(self, "is_active", False)

    def is_approved(self) -> bool:
        return self.status in {
            RiskRuleStatus.APPROVED,
            RiskRuleStatus.ACTIVE,
        }

    def is_approved_active(self) -> bool:
        return self.status == RiskRuleStatus.ACTIVE and self.is_active

    def covers_period(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> bool:
        self._validate_effective_period()
        period_start = _comparable_datetime(period_start)
        period_end = _comparable_datetime(period_end)
        effective_from = _comparable_datetime(self.effective_from)
        effective_to = _comparable_datetime(self.effective_to)

        if effective_from and effective_from > period_start:
            return False

        if effective_to and effective_to < period_end:
            return False

        return True

    def overlaps_effective_period(
        self,
        other: "RiskRuleVersion"
    ) -> bool:
        self_start = _comparable_datetime(self.effective_from) or datetime.min
        self_end = _comparable_datetime(self.effective_to) or datetime.max
        other_start = _comparable_datetime(other.effective_from) or datetime.min
        other_end = _comparable_datetime(other.effective_to) or datetime.max

        return self_start <= other_end and other_start <= self_end

    def _validate_effective_period(self) -> None:
        if (
            self.effective_from
            and self.effective_to
            and _comparable_datetime(self.effective_from)
            > _comparable_datetime(self.effective_to)
        ):
            raise ValueError(
                "effective_from must be before or equal to effective_to."
            )


@dataclass
class RiskAssessmentRequest:
    risk_definition_id: str
    period_start: datetime
    period_end: datetime
    entity_type: str
    entity_id: str
    kpi_result_ids: list[str] = field(default_factory=list)
    kpi_results: list[KPICalculationResult] = field(default_factory=list)
    metric_values: dict[str, float] = field(default_factory=dict)
    source_reference: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    assessment_run_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        _require_text(self.risk_definition_id, "risk_definition_id")
        _require_text(self.entity_type, "entity_type")
        _require_text(self.entity_id, "entity_id")
        _require_text(self.assessment_run_id, "assessment_run_id")

        if self.period_start > self.period_end:
            raise ValueError("period_start must be before or equal to period_end.")


@dataclass
class RiskRuleEvaluation:
    risk_level: RiskLevel
    risk_score: float
    reason: str
    triggered: bool = True
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.risk_level = RiskLevel.from_value(self.risk_level)
        self.risk_score = float(self.risk_score)
        _require_text(self.reason, "reason")


@dataclass
class RiskAssessmentResult:
    tenant_id: str
    risk_definition_id: str
    rule_version_id: str
    rule_version_number: str
    entity_type: str
    entity_id: str
    period_start: datetime
    period_end: datetime
    risk_score: float
    risk_level: RiskLevel
    status: RiskAssessmentStatus
    reason: str
    evidence: dict[str, Any]
    source_reference: str
    assessment_run_id: str
    risk_definition_version: str
    kpi_result_ids: list[str]
    formula_versions: list[dict[str, str]]
    source_record_ids: list[str]
    source_validation_lineage: dict[str, Any]
    lineage_id: str
    result_id: str = field(default_factory=lambda: str(uuid4()))
    assessed_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.result_id, "result_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.risk_definition_id, "risk_definition_id")
        _require_text(self.rule_version_id, "rule_version_id")
        _require_text(self.rule_version_number, "rule_version_number")
        _require_text(self.entity_type, "entity_type")
        _require_text(self.entity_id, "entity_id")
        _require_text(self.reason, "reason")
        _require_text(self.assessment_run_id, "assessment_run_id")
        _require_text(self.risk_definition_version, "risk_definition_version")
        _require_text(self.lineage_id, "lineage_id")
        self.risk_level = RiskLevel.from_value(self.risk_level)
        self.status = RiskAssessmentStatus.from_value(self.status)
        self.risk_score = float(self.risk_score)

        if not self.kpi_result_ids:
            raise ValueError("RiskAssessmentResult requires KPI result lineage.")

        if not self.formula_versions:
            raise ValueError("RiskAssessmentResult requires formula lineage.")

        if self.period_start > self.period_end:
            raise ValueError("period_start must be before or equal to period_end.")


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")


def _comparable_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)
