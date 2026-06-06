from datetime import datetime
from pathlib import Path

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import KPIDomain, KPILifecycle
from app.models.kpi_calculation import KPICalculationRequest, KPISourceData
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceRecord,
    OperationalSourceType,
    SourceQualityStatus,
    SourceRegistryEntry,
    SourceValidationStatus,
)
from app.services.database_service import DatabaseService
from app.services.formula_handler_registry import (
    CountRecordsHandler,
    FormulaHandlerRegistry,
)
from app.services.formula_version_service import FormulaVersionService
from app.services.kpi_audit_service import KPIAuditService
from app.services.kpi_calculation_service import KPICalculationService
from app.services.kpi_source_eligibility_service import (
    KPISourceEligibilityService,
)
from app.services.kpi_registry_service import KPIRegistryService
from app.services.sqlite_operational_source_repository import (
    SQLiteOperationalSourceRepository,
)
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_kpi_calculation_result_repository import (
    SQLiteKPICalculationResultRepository,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)
from app.services.sqlite_source_registry_repository import (
    SQLiteSourceRegistryRepository,
)


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
    source_registry_repository = SQLiteSourceRegistryRepository(database)
    source_repository = SQLiteOperationalSourceRepository(database)
    source_eligibility_service = KPISourceEligibilityService(
        source_registry_repository,
        source_repository,
        audit_service,
    )

    return {
        "audit_repository": audit_repository,
        "calculation_service": KPICalculationService(
            definition_repository,
            formula_service,
            handler_registry,
            result_repository,
            audit_service,
            source_eligibility_service=source_eligibility_service,
        ),
        "definition_repository": definition_repository,
        "registry_service": registry_service,
        "result_repository": result_repository,
        "source_registry_repository": source_registry_repository,
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


def calculation_request(tenant_id="tenant-1"):
    return KPICalculationRequest(
        kpi_id="csat",
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        source_data=KPISourceData(
            tenant_id=tenant_id,
            records=[
                {"contact_id": "C001"},
            ],
            source_reference="survey:test",
        ),
    )


def source_registry_entry():
    return SourceRegistryEntry(
        tenant_id="tenant-1",
        source_type=OperationalSourceType.SURVEY,
        source_name="Survey",
        source_owner="owner-1",
        source_steward="steward-1",
        allowed_entity_scopes=[OperationalEntityScope.AGENT],
    )


def operational_source(tenant_id="tenant-1"):
    return OperationalSourceRecord(
        tenant_id=tenant_id,
        source_record_id="source-1",
        source_type=OperationalSourceType.SURVEY,
        source_reference="survey:2026-03",
        source_version="v1",
        lineage_id="lineage-1",
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        entity_type=OperationalEntityScope.AGENT,
        entity_id="agent-1",
        metric_values={"csat": 92},
        validation_status=SourceValidationStatus.VALID,
        data_quality_status=SourceQualityStatus.VALID,
    )


def test_missing_tenant_context_rejected(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)

    with pytest.raises(ValueError, match="TenantContext required"):
        services["calculation_service"].calculate_kpi(
            None,
            calculation_request()
        )


def test_unauthorized_calculation_rejected_and_audited(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    unauthorized = TenantContext(
        tenant_id="tenant-1",
        user_id="steward-1",
        roles={GovernanceRole.KPI_STEWARD.value},
    )

    with pytest.raises(PermissionError, match="calculate_kpi"):
        services["calculation_service"].calculate_kpi(
            unauthorized,
            calculation_request()
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
    assert "CALCULATION_REJECTED" in actions


def test_cross_tenant_source_data_rejected(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)

    with pytest.raises(PermissionError, match="source data tenant"):
        services["calculation_service"].calculate_kpi(
            context(),
            calculation_request(tenant_id="tenant-2")
        )


def test_cross_tenant_operational_source_usage_rejected_and_audited(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    services["source_registry_repository"].upsert_entry(
        context(GovernanceRole.GOVERNANCE_ADMIN),
        source_registry_entry()
    )
    request = calculation_request()
    request.source_records = [
        operational_source(tenant_id="tenant-2")
    ]

    with pytest.raises(PermissionError, match="tenant"):
        services["calculation_service"].calculate_kpi(
            context(),
            request
        )

    assert "SOURCE_ACCESS_DENIED" in [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]


def test_cross_tenant_kpi_access_rejected_without_leakage(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    tenant_two = context(
        tenant_id="tenant-2",
        user_id="tenant-two-owner"
    )

    with pytest.raises(ValueError, match="not found"):
        services["calculation_service"].calculate_kpi(
            tenant_two,
            calculation_request(tenant_id="tenant-2")
        )


def test_cross_tenant_formula_access_is_filtered(tmp_path):
    services = create_services(tmp_path)
    formula = create_active_kpi(services)

    assert services["definition_repository"].get_formula_version(
        context(tenant_id="tenant-2"),
        formula.formula_version_id
    ) is None


def test_cross_tenant_result_retrieval_is_filtered(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    result = services["calculation_service"].calculate_kpi(
        context(),
        calculation_request()
    )
    tenant_two = context(tenant_id="tenant-2")

    assert services["result_repository"].get_result(
        tenant_two,
        result.result_id
    ) is None


def test_cross_tenant_audit_retrieval_is_filtered(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    services["calculation_service"].calculate_kpi(
        context(),
        calculation_request()
    )

    assert services["audit_repository"].list_events(
        context(tenant_id="tenant-2")
    ) == []


def test_unauthorized_result_access_rejected(tmp_path):
    services = create_services(tmp_path)
    create_active_kpi(services)
    result = services["calculation_service"].calculate_kpi(
        context(),
        calculation_request()
    )
    unauthorized = TenantContext(
        tenant_id="tenant-1",
        user_id="user-1",
        roles=set(),
    )

    with pytest.raises(PermissionError, match="view_kpi_results"):
        services["result_repository"].get_result(
            unauthorized,
            result.result_id
        )


def test_formula_execution_does_not_use_dynamic_code_execution():
    files = [
        Path("app/services/formula_handler_registry.py"),
        Path("app/services/kpi_calculation_service.py"),
    ]
    forbidden_tokens = [
        "ev" + "al(",
        "ex" + "ec(",
        "com" + "pile(",
    ]
    combined_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in files
    )

    for token in forbidden_tokens:
        assert token not in combined_text
