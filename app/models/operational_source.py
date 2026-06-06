from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.kpi import utc_now


class OperationalSourceType(Enum):
    SURVEY = "survey"
    QA = "qa"
    CALL = "call"
    TRANSCRIPT = "transcript"
    WORKFORCE = "workforce"
    ATTENDANCE = "attendance"
    ADHERENCE = "adherence"
    AUX = "aux"
    PRODUCTIVITY = "productivity"
    SALES = "sales"
    CUSTOM = "custom"

    @classmethod
    def from_value(
        cls,
        value: "OperationalSourceType | str"
    ) -> "OperationalSourceType":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for source_type in cls:
            if source_type.value == normalized or source_type.name.lower() == normalized:
                return source_type

        raise ValueError(f"Unsupported operational source type: {value}")


class OperationalEntityScope(Enum):
    TENANT = "tenant"
    TEAM = "team"
    AGENT = "agent"
    CONTACT = "contact"
    QUEUE = "queue"
    CAMPAIGN = "campaign"

    @classmethod
    def from_value(
        cls,
        value: "OperationalEntityScope | str"
    ) -> "OperationalEntityScope":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for scope in cls:
            if scope.value == normalized or scope.name.lower() == normalized:
                return scope

        raise ValueError(f"Unsupported operational entity scope: {value}")


class SourceValidationStatus(Enum):
    PENDING = "pending"
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"

    @classmethod
    def from_value(
        cls,
        value: "SourceValidationStatus | str"
    ) -> "SourceValidationStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for status in cls:
            if status.value == normalized or status.name.lower() == normalized:
                return status

        raise ValueError(f"Unsupported source validation status: {value}")


class SourceQualityStatus(Enum):
    VALID = "valid"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_PERIOD = "invalid_period"
    TENANT_MISMATCH = "tenant_mismatch"
    UNSUPPORTED_SOURCE_TYPE = "unsupported_source_type"
    DUPLICATE_SOURCE = "duplicate_source"
    STALE_SOURCE = "stale_source"
    INVALID_ENTITY_SCOPE = "invalid_entity_scope"
    INVALID_METRIC_VALUE = "invalid_metric_value"
    DATA_CONFLICT = "data_conflict"

    @classmethod
    def from_value(
        cls,
        value: "SourceQualityStatus | str"
    ) -> "SourceQualityStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for status in cls:
            if status.value == normalized or status.name.lower() == normalized:
                return status

        raise ValueError(f"Unsupported source quality status: {value}")


class SourceQualityDimension(Enum):
    ACCURACY = "accuracy"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"

    @classmethod
    def from_value(
        cls,
        value: "SourceQualityDimension | str"
    ) -> "SourceQualityDimension":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")

        for dimension in cls:
            if dimension.value == normalized or dimension.name.lower() == normalized:
                return dimension

        raise ValueError(f"Unsupported source quality dimension: {value}")


@dataclass
class SourceRegistryEntry:
    tenant_id: str
    source_type: OperationalSourceType
    source_name: str
    source_owner: str
    source_steward: str
    allowed_entity_scopes: list[OperationalEntityScope] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    numeric_fields: list[str] = field(default_factory=list)
    freshness_threshold_hours: int | None = None
    is_active: bool = True
    created_by: str = ""
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.source_name, "source_name")
        _require_text(self.source_owner, "source_owner")
        _require_text(self.source_steward, "source_steward")
        self.source_type = OperationalSourceType.from_value(self.source_type)
        self.allowed_entity_scopes = [
            OperationalEntityScope.from_value(scope)
            for scope in self.allowed_entity_scopes
        ]
        self.required_fields = _normalized_text_list(self.required_fields)
        self.numeric_fields = _normalized_text_list(self.numeric_fields)

        if (
            self.freshness_threshold_hours is not None
            and self.freshness_threshold_hours < 0
        ):
            raise ValueError("freshness_threshold_hours cannot be negative.")


@dataclass
class OperationalSourceRecord:
    tenant_id: str
    source_type: OperationalSourceType
    source_reference: str
    source_version: str
    lineage_id: str
    period_start: datetime | None
    period_end: datetime | None
    entity_type: OperationalEntityScope = OperationalEntityScope.TENANT
    metric_values: dict[str, Any] = field(default_factory=dict)
    source_record_id: str = field(default_factory=lambda: str(uuid4()))
    entity_id: str = ""
    validation_status: SourceValidationStatus = SourceValidationStatus.PENDING
    data_quality_status: SourceQualityStatus = SourceQualityStatus.VALID
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.source_record_id, "source_record_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.source_version, "source_version")
        _require_text(self.lineage_id, "lineage_id")
        self.source_type = OperationalSourceType.from_value(self.source_type)
        self.entity_type = OperationalEntityScope.from_value(self.entity_type)
        self.validation_status = SourceValidationStatus.from_value(
            self.validation_status
        )
        self.data_quality_status = SourceQualityStatus.from_value(
            self.data_quality_status
        )


@dataclass
class SourceValidationResult:
    tenant_id: str
    source_record_id: str
    source_type: OperationalSourceType
    validation_status: SourceValidationStatus
    data_quality_status: SourceQualityStatus
    quality_issues: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""
    validation_event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.validation_event_id, "validation_event_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.source_record_id, "source_record_id")
        self.source_type = OperationalSourceType.from_value(self.source_type)
        self.validation_status = SourceValidationStatus.from_value(
            self.validation_status
        )
        self.data_quality_status = SourceQualityStatus.from_value(
            self.data_quality_status
        )
        self.quality_issues = [
            _validated_quality_issue(issue)
            for issue in self.quality_issues
        ]


def source_quality_issue(
    dimension: SourceQualityDimension | str,
    code: SourceQualityStatus | str,
    field_name: str = "",
    message: str = ""
) -> dict[str, Any]:
    return {
        "dimension": SourceQualityDimension.from_value(dimension).value,
        "code": SourceQualityStatus.from_value(code).value,
        "field_name": field_name,
        "message": message,
    }


def _validated_quality_issue(issue: dict[str, Any]) -> dict[str, Any]:
    validated = dict(issue)
    validated["dimension"] = SourceQualityDimension.from_value(
        validated.get("dimension", "")
    ).value

    if "code" in validated:
        validated["code"] = SourceQualityStatus.from_value(
            validated["code"]
        ).value

    return validated


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")


def _normalized_text_list(values: list[str]) -> list[str]:
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]
