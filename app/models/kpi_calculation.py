from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.models.kpi import utc_now
from app.models.operational_source import OperationalSourceRecord


class KPICalculationStatus(Enum):
    SUCCESS = "success"
    FAILED_VALIDATION = "failed_validation"
    MISSING_FORMULA = "missing_formula"
    FORMULA_CONFLICT = "formula_conflict"
    CALCULATION_ERROR = "calculation_error"
    REJECTED = "rejected"

    @classmethod
    def from_value(
        cls,
        value: "KPICalculationStatus | str"
    ) -> "KPICalculationStatus":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().lower().replace(" ", "_")

        for status in cls:
            if status.value == normalized or status.name.lower() == normalized:
                return status

        raise ValueError(f"Unsupported KPI calculation status: {value}")


@dataclass
class KPISourceData:
    tenant_id: str
    records: list[dict[str, Any]] = field(default_factory=list)
    source_reference: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "tenant_id")


@dataclass
class KPICalculationRequest:
    kpi_id: str
    period_start: datetime
    period_end: datetime
    source_data: KPISourceData
    scope: dict[str, Any] = field(default_factory=dict)
    source_records: list[OperationalSourceRecord] = field(default_factory=list)
    source_record_ids: list[str] = field(default_factory=list)
    source_references: list[str] = field(default_factory=list)
    calculation_run_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        _require_text(self.kpi_id, "kpi_id")
        _require_text(self.calculation_run_id, "calculation_run_id")


@dataclass
class FormulaHandlerResult:
    value: float
    data_quality_status: str = "valid"
    source_reference: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.data_quality_status, "data_quality_status")


@dataclass
class KPICalculationResult:
    tenant_id: str
    kpi_id: str
    formula_version_id: str
    formula_version_number: str
    period_start: datetime
    period_end: datetime
    scope: dict[str, Any]
    value: float | None
    status: KPICalculationStatus
    data_quality_status: str
    source_reference: str
    calculation_run_id: str
    result_id: str = field(default_factory=lambda: str(uuid4()))
    calculated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.result_id, "result_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.kpi_id, "kpi_id")
        _require_text(self.formula_version_id, "formula_version_id")
        _require_text(self.formula_version_number, "formula_version_number")
        _require_text(self.data_quality_status, "data_quality_status")
        _require_text(self.calculation_run_id, "calculation_run_id")
        self.status = KPICalculationStatus.from_value(self.status)

        if self.period_start > self.period_end:
            raise ValueError("period_start must be before or equal to period_end.")


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")
