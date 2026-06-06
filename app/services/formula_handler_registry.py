from typing import Any, Protocol

from app.models.kpi import FormulaVersion
from app.models.kpi_calculation import (
    FormulaHandlerResult,
    KPICalculationRequest,
)


class FormulaHandler(Protocol):
    def calculate(
        self,
        request: KPICalculationRequest,
        formula_version: FormulaVersion
    ) -> FormulaHandlerResult | float:
        ...


class FormulaHandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, FormulaHandler] = {}

    def register(
        self,
        key: str,
        handler: FormulaHandler
    ) -> None:
        normalized_key = self._normalize_key(key)

        if not normalized_key:
            raise ValueError("Formula handler key is required.")

        if normalized_key in self._handlers:
            raise ValueError(f"Formula handler already registered: {normalized_key}")

        if not hasattr(handler, "calculate"):
            raise TypeError("Formula handler must provide a calculate method.")

        self._handlers[normalized_key] = handler

    def get_handler(self, key: str) -> FormulaHandler | None:
        normalized_key = self._normalize_key(key)

        if not normalized_key:
            raise ValueError("Formula handler key is required.")

        return self._handlers.get(normalized_key)

    def require_handler(self, key: str) -> FormulaHandler:
        handler = self.get_handler(key)

        if handler is None:
            raise KeyError(f"Unknown formula handler: {key}")

        return handler

    def _normalize_key(self, key: str) -> str:
        return str(key).strip().lower()


class CountRecordsHandler:
    def calculate(
        self,
        request: KPICalculationRequest,
        formula_version: FormulaVersion
    ) -> FormulaHandlerResult:
        return FormulaHandlerResult(
            value=float(len(request.source_data.records)),
            source_reference=request.source_data.source_reference,
            metadata={
                "handler_key": formula_version.expression,
            },
        )


class FieldAverageHandler:
    def __init__(self, field_name: str):
        self.field_name = field_name

    def calculate(
        self,
        request: KPICalculationRequest,
        formula_version: FormulaVersion
    ) -> FormulaHandlerResult:
        values = [
            float(record[self.field_name])
            for record in request.source_data.records
            if self._has_numeric_field(record)
        ]

        if not values:
            return FormulaHandlerResult(
                value=0.0,
                data_quality_status="no_valid_values",
                source_reference=request.source_data.source_reference,
            )

        return FormulaHandlerResult(
            value=sum(values) / len(values),
            source_reference=request.source_data.source_reference,
            metadata={
                "field_name": self.field_name,
                "record_count": len(values),
            },
        )

    def _has_numeric_field(self, record: dict[str, Any]) -> bool:
        try:
            float(record[self.field_name])
            return True
        except (KeyError, TypeError, ValueError):
            return False
