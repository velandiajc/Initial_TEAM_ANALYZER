from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import KPIDomain, KPILifecycle
from app.models.kpi_calculation import (
    KPICalculationRequest,
    KPICalculationStatus,
    KPISourceData,
)
from app.services.database_service import DatabaseService
from app.services.formula_handler_registry import (
    CountRecordsHandler,
    FormulaHandlerRegistry,
)
from app.services.formula_version_service import FormulaVersionService
from app.services.kpi_audit_service import KPIAuditService
from app.services.kpi_calculation_service import KPICalculationRejectedError
from app.services.kpi_calculation_service import KPICalculationService
from app.services.kpi_registry_service import KPIRegistryService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_kpi_calculation_result_repository import (
    SQLiteKPICalculationResultRepository,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)


class FailingHandler:
    def calculate(self, request, formula_version):
        raise RuntimeError("source data unavailable")


def context(role=GovernanceRole.KPI_OWNER, tenant_id="tenant-1", user_id="owner-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles={role.value},
    )


def create_services(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    definition_repository = SQLiteKPIDefinitionRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)
    registry_service = KPIRegistryService(
        definition_repository,
        audit_service
    )
    formula_service = FormulaVersionService(definition_repository)
    handler_registry = FormulaHandlerRegistry()
    handler_registry.register(
        "count_records",
        CountRecordsHandler()
    )
    result_repository = SQLiteKPICalculationResultRepository(database)

    return {
        "audit_repository": audit_repository,
        "audit_service": audit_service,
        "calculation_service": KPICalculationService(
            definition_repository,
            formula_service,
            handler_registry,
            result_repository,
            audit_service,
        ),
        "definition_repository": definition_repository,
        "registry_service": registry_service,
        "result_repository": result_repository,
    }


def create_active_kpi(services):
    owner = context()
    approver = context(
        GovernanceRole.KPI_APPROVER,
        user_id="approver-1"
    )
    registry = services["registry_service"]
    registry.register_kpi(
        owner,
        kpi_id="csat",
        name="CSAT",
        domain=KPIDomain.CUSTOMER_EXPERIENCE,
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    formula = registry.submit_formula_version(
        owner,
        kpi_id="csat",
        version="1.0",
        expression="count_records",
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )
    registry.approve_formula_version(
        approver,
        formula.formula_version_id
    )
    registry.change_lifecycle(
        approver,
        kpi_id="csat",
        lifecycle=KPILifecycle.ACTIVE,
    )

    return formula


def calculation_request(tenant_id="tenant-1", kpi_id="csat"):
    return KPICalculationRequest(
        kpi_id=kpi_id,
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        source_data=KPISourceData(
            tenant_id=tenant_id,
            records=[
                {"contact_id": "C001"},
                {"contact_id": "C002"},
                {"contact_id": "C003"},
            ],
            source_reference="survey:unit-test",
        ),
        scope={
            "team": "support"
        },
    )


def test_calculation_persists_successful_result_with_lineage(tmp_path):
    services = create_services(tmp_path)
    formula = create_active_kpi(services)

    result = services["calculation_service"].calculate_kpi(
        context(),
        calculation_request()
    )
    persisted = services["result_repository"].get_result(
        context(),
        result.result_id
    )

    assert result.status == KPICalculationStatus.SUCCESS
    assert result.value == 3.0
    assert persisted is not None
    assert persisted.tenant_id == "tenant-1"
    assert persisted.formula_version_id == formula.formula_version_id
    assert persisted.formula_version_number == "1.0"


def test_calculation_generates_success_audit_events(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)

    result = services["calculation_service"].calculate_kpi(
        context(),
        calculation_request()
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert "CALCULATION_REQUESTED" in actions
    assert "CALCULATION_STARTED" in actions
    assert "FORMULA_SELECTED" in actions
    assert "CALCULATION_COMPLETED" in actions
    assert result.calculation_run_id


def test_inactive_kpi_is_rejected_and_audited(tmp_path):
    services = create_services(tmp_path)
    services["registry_service"].register_kpi(
        context(),
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )

    with pytest.raises(KPICalculationRejectedError, match="active"):
        services["calculation_service"].calculate_kpi(
            context(),
            calculation_request()
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
    assert "CALCULATION_REJECTED" in actions


def test_invalid_date_range_is_rejected_and_audited(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    request = KPICalculationRequest(
        kpi_id="csat",
        period_start=datetime(2026, 4, 1),
        period_end=datetime(2026, 3, 1),
        source_data=KPISourceData(
            tenant_id="tenant-1",
            records=[],
        ),
    )

    with pytest.raises(KPICalculationRejectedError, match="period_start"):
        services["calculation_service"].calculate_kpi(
            context(),
            request
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
    assert "CALCULATION_REJECTED" in actions


def test_unknown_handler_rejects_calculation_and_does_not_persist_result(tmp_path):
    services = create_services(tmp_path)
    owner = context()
    approver = context(
        GovernanceRole.KPI_APPROVER,
        user_id="approver-1"
    )
    registry = services["registry_service"]
    registry.register_kpi(
        owner,
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    formula = registry.submit_formula_version(
        owner,
        kpi_id="csat",
        version="1.0",
        expression="not_registered",
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )
    registry.approve_formula_version(
        approver,
        formula.formula_version_id
    )
    registry.change_lifecycle(
        approver,
        "csat",
        KPILifecycle.ACTIVE
    )

    with pytest.raises(KeyError, match="Unknown formula handler"):
        services["calculation_service"].calculate_kpi(
            owner,
            calculation_request()
        )

    assert services["result_repository"].list_results_for_kpi(owner, "csat") == []


def test_result_view_generates_audit_event(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    result = services["calculation_service"].calculate_kpi(
        context(),
        calculation_request()
    )

    viewed = services["calculation_service"].get_result(
        context(),
        result.result_id
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert viewed is not None
    assert "RESULT_VIEWED" in actions


def test_handler_failure_generates_failed_audit_event(tmp_path):
    services = create_services(tmp_path)
    services["calculation_service"].formula_handler_registry.register(
        "failing_handler",
        FailingHandler()
    )
    owner = context()
    approver = context(
        GovernanceRole.KPI_APPROVER,
        user_id="approver-1"
    )
    registry = services["registry_service"]
    registry.register_kpi(
        owner,
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    formula = registry.submit_formula_version(
        owner,
        kpi_id="csat",
        version="1.0",
        expression="failing_handler",
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )
    registry.approve_formula_version(
        approver,
        formula.formula_version_id
    )
    registry.change_lifecycle(
        approver,
        "csat",
        KPILifecycle.ACTIVE
    )

    with pytest.raises(RuntimeError, match="source data unavailable"):
        services["calculation_service"].calculate_kpi(
            owner,
            calculation_request()
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
    assert "CALCULATION_FAILED" in actions
