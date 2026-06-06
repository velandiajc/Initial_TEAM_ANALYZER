from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KPIDomain(Enum):
    CUSTOMER_EXPERIENCE = "customer_experience"
    QUALITY = "quality"
    WORKFORCE = "workforce"
    PRODUCTIVITY = "productivity"
    SALES = "sales"
    COACHING = "coaching"
    OPERATIONS = "operations"

    @classmethod
    def from_value(cls, value: "KPIDomain | str") -> "KPIDomain":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for domain in cls:
            if domain.value == normalized or domain.name.lower() == normalized:
                return domain

        raise ValueError(f"Unsupported KPI domain: {value}")


class KPILifecycle(Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    RETIRED = "retired"
    ARCHIVED = "archived"

    @classmethod
    def from_value(cls, value: "KPILifecycle | str") -> "KPILifecycle":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for lifecycle in cls:
            if lifecycle.value == normalized or lifecycle.name.lower() == normalized:
                return lifecycle

        raise ValueError(f"Unsupported KPI lifecycle: {value}")


class FormulaStatus(Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETIRED = "retired"

    @classmethod
    def from_value(cls, value: "FormulaStatus | str") -> "FormulaStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for status in cls:
            if status.value == normalized or status.name.lower() == normalized:
                return status

        raise ValueError(f"Unsupported formula status: {value}")


@dataclass
class KPIThreshold:
    threshold_id: str
    tenant_id: str
    kpi_id: str
    name: str
    risk_level: str
    target: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    created_by: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_text(self.threshold_id, "threshold_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.kpi_id, "kpi_id")
        _require_text(self.name, "name")
        _require_text(self.risk_level, "risk_level")

        if self.target is None and self.minimum is None and self.maximum is None:
            raise ValueError(
                "KPIThreshold requires at least one governed threshold value."
            )


@dataclass
class FormulaVersion:
    formula_version_id: str
    tenant_id: str
    kpi_id: str
    version: str
    expression: str
    created_by: str
    status: FormulaStatus = FormulaStatus.PENDING_APPROVAL
    approved_by: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    approved_at: datetime | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _require_text(self.formula_version_id, "formula_version_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.kpi_id, "kpi_id")
        _require_text(self.version, "version")
        _require_text(self.expression, "expression")
        _require_text(self.created_by, "created_by")
        self.status = FormulaStatus.from_value(self.status)

    def approve(
        self,
        approver_user_id: str,
        approved_at: datetime | None = None
    ) -> None:
        _require_text(approver_user_id, "approver_user_id")

        if approver_user_id == self.created_by:
            raise PermissionError("Creator cannot approve own formula.")

        self.status = FormulaStatus.APPROVED
        self.approved_by = approver_user_id
        self.approved_at = approved_at or utc_now()

    def is_approved(self) -> bool:
        return self.status == FormulaStatus.APPROVED


@dataclass
class KPIDefinition:
    kpi_id: str
    tenant_id: str
    name: str
    domain: KPIDomain
    owner_user_id: str
    steward_user_id: str
    lifecycle: KPILifecycle = KPILifecycle.DRAFT
    description: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    thresholds: list[KPIThreshold] = field(default_factory=list)
    formula_versions: list[FormulaVersion] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.kpi_id, "kpi_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.name, "name")
        _require_text(self.owner_user_id, "owner_user_id")
        _require_text(self.steward_user_id, "steward_user_id")
        self.domain = KPIDomain.from_value(self.domain)
        self.lifecycle = KPILifecycle.from_value(self.lifecycle)

    def move_to_lifecycle(self, lifecycle: KPILifecycle | str) -> None:
        self.lifecycle = KPILifecycle.from_value(lifecycle)
        self.updated_at = utc_now()

    def add_threshold(self, threshold: KPIThreshold) -> None:
        if threshold.tenant_id != self.tenant_id:
            raise ValueError("Threshold tenant does not match KPI definition tenant.")

        if threshold.kpi_id != self.kpi_id:
            raise ValueError("Threshold KPI does not match KPI definition.")

        self.thresholds.append(threshold)
        self.updated_at = utc_now()

    def add_formula_version(self, formula_version: FormulaVersion) -> None:
        if formula_version.tenant_id != self.tenant_id:
            raise ValueError("Formula tenant does not match KPI definition tenant.")

        if formula_version.kpi_id != self.kpi_id:
            raise ValueError("Formula KPI does not match KPI definition.")

        self.formula_versions.append(formula_version)
        self.updated_at = utc_now()


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")
