from datetime import datetime

import pytest

from app.models.kpi import FormulaVersion
from app.models.kpi_calculation import KPICalculationRequest, KPISourceData
from app.services.formula_handler_registry import (
    CountRecordsHandler,
    FormulaHandlerRegistry,
)


def request():
    return KPICalculationRequest(
        kpi_id="csat",
        period_start=datetime(2026, 1, 1),
        period_end=datetime(2026, 1, 31),
        source_data=KPISourceData(
            tenant_id="tenant-1",
            records=[
                {"contact_id": "1"},
                {"contact_id": "2"},
            ],
            source_reference="survey:test",
        ),
    )


def formula():
    return FormulaVersion(
        formula_version_id="formula-1",
        tenant_id="tenant-1",
        kpi_id="csat",
        version="1.0",
        expression="count_records",
        created_by="owner-1",
    )


def test_registry_registers_and_resolves_handler():
    registry = FormulaHandlerRegistry()
    handler = CountRecordsHandler()

    registry.register("count_records", handler)

    assert registry.require_handler("count_records") is handler


def test_registry_rejects_empty_handler_key():
    registry = FormulaHandlerRegistry()

    with pytest.raises(ValueError, match="key is required"):
        registry.register("", CountRecordsHandler())


def test_registry_rejects_duplicate_handler_key():
    registry = FormulaHandlerRegistry()
    registry.register("count_records", CountRecordsHandler())

    with pytest.raises(ValueError, match="already registered"):
        registry.register("count_records", CountRecordsHandler())


def test_registry_rejects_unknown_handler_key():
    registry = FormulaHandlerRegistry()

    with pytest.raises(KeyError, match="Unknown formula handler"):
        registry.require_handler("unknown")


def test_handler_executes_through_registry_without_raw_text_execution():
    registry = FormulaHandlerRegistry()
    registry.register("count_records", CountRecordsHandler())

    result = registry.require_handler("count_records").calculate(
        request(),
        formula()
    )

    assert result.value == 2.0
    assert result.source_reference == "survey:test"
