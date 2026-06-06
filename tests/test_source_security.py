from datetime import datetime

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
    SourceValidationResult,
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
from app.services.kpi_registry_service import KPIRegistryService
from app.services.kpi_source_eligibility_service import (
    KPISourceEligibilityService,
)
from app.services.source_registry_service import SourceRegistryService
from app.services.source_validation_service import SourceValidationService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_kpi_calculation_result_repository import (
    SQLiteKPICalculationResultRepository,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)
from app.services.sqlite_operational_source_repository import (
    SQLiteOperationalSourceRepository,
)
from app.services.sqlite_source_registry_repository import (
    SQLiteSourceRegistryRepository,
)
from app.services.sqlite_source_validation_repository import (
    SQLiteSourceValidationRepository,
)


def context(role=GovernanceRole.GOVERNANCE_ADMIN, tenant_id="tenant-1"):
    role_value = getattr(role, "value", role)

    return TenantContext(
        tenant_id=tenant_id,
        user_id="user-1",
        roles={role_value} if role_value else set(),
    )


def source_entry(
    tenant_id="tenant-1",
    source_type=OperationalSourceType.SURVEY,
    is_active=True
):
    return SourceRegistryEntry(
        tenant_id=tenant_id,
        source_type=source_type,
        source_name="Survey",
        source_owner="owner-1",
        source_steward="steward-1",
        allowed_entity_scopes=[OperationalEntityScope.AGENT],
        required_fields=["csat"],
        numeric_fields=["csat"],
        is_active=is_active,
    )


def source_record(tenant_id="tenant-1", source_record_id="source-1"):
    return OperationalSourceRecord(
        tenant_id=tenant_id,
        source_record_id=source_record_id,
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


def validation_result(tenant_id="tenant-1"):
    return SourceValidationResult(
        tenant_id=tenant_id,
        source_record_id="source-1",
        source_type=OperationalSourceType.SURVEY,
        validation_status=SourceValidationStatus.VALID,
        data_quality_status=SourceQualityStatus.VALID,
    )


def create_source_stack(tmp_path):
    database = DatabaseService(tmp_path / "security.db")
    database.initialize()
    source_registry_repository = SQLiteSourceRegistryRepository(database)
    source_repository = SQLiteOperationalSourceRepository(database)
    validation_repository = SQLiteSourceValidationRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)

    source_registry_repository.upsert_entry(
        context(),
        source_entry()
    )

    return {
        "audit_repository": audit_repository,
        "audit_service": audit_service,
        "registry_repository": source_registry_repository,
        "source_repository": source_repository,
        "validation_repository": validation_repository,
        "registry_service": SourceRegistryService(
            source_registry_repository,
            audit_service,
        ),
        "validation_service": SourceValidationService(
            source_registry_repository,
            source_repository,
            validation_repository,
            audit_service,
        ),
        "eligibility_service": KPISourceEligibilityService(
            source_registry_repository,
            source_repository,
            audit_service,
        ),
    }


def create_calculation_stack(tmp_path):
    stack = create_source_stack(tmp_path)
    database = stack["registry_repository"].database_service
    definition_repository = SQLiteKPIDefinitionRepository(database)
    audit_service = stack["audit_service"]
    registry_service = KPIRegistryService(
        definition_repository,
        audit_service
    )
    formula_service = FormulaVersionService(definition_repository)
    handler_registry = FormulaHandlerRegistry()
    handler_registry.register("count_records", CountRecordsHandler())
    result_repository = SQLiteKPICalculationResultRepository(database)
    calculation_service = KPICalculationService(
        definition_repository,
        formula_service,
        handler_registry,
        result_repository,
        audit_service,
        source_eligibility_service=stack["eligibility_service"],
    )
    owner = TenantContext(
        tenant_id="tenant-1",
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )
    approver = TenantContext(
        tenant_id="tenant-1",
        user_id="approver-1",
        roles={GovernanceRole.KPI_APPROVER.value},
    )
    registry_service.register_kpi(
        owner,
        kpi_id="csat",
        name="CSAT",
        domain=KPIDomain.CUSTOMER_EXPERIENCE,
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    formula = registry_service.submit_formula_version(
        owner,
        kpi_id="csat",
        version="1.0",
        expression="count_records",
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )
    registry_service.approve_formula_version(
        approver,
        formula.formula_version_id
    )
    registry_service.change_lifecycle(
        approver,
        "csat",
        KPILifecycle.ACTIVE
    )
    stack["calculation_service"] = calculation_service
    stack["owner"] = owner

    return stack


def calculation_request():
    return KPICalculationRequest(
        kpi_id="csat",
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        source_data=KPISourceData(
            tenant_id="tenant-1",
            records=[{"contact_id": "C001"}],
            source_reference="survey:test",
        ),
        source_records=[source_record(tenant_id="tenant-2")],
    )


def test_cross_tenant_source_validation_rejected(tmp_path):
    stack = create_source_stack(tmp_path)

    with pytest.raises(PermissionError, match="tenant"):
        stack["validation_service"].validate_source(
            context(),
            source_record(tenant_id="tenant-2")
        )


def test_cross_tenant_source_persistence_rejected(tmp_path):
    stack = create_source_stack(tmp_path)

    with pytest.raises(PermissionError, match="tenant-scoped"):
        stack["source_repository"].save(
            context(),
            source_record(tenant_id="tenant-2")
        )


def test_cross_tenant_source_retrieval_filtered(tmp_path):
    stack = create_source_stack(tmp_path)
    stack["source_repository"].save(
        context(),
        source_record()
    )

    assert stack["source_repository"].get_record(
        context(tenant_id="tenant-2"),
        "source-1"
    ) is None


def test_cross_tenant_source_usage_in_calculation_rejected(tmp_path):
    stack = create_calculation_stack(tmp_path)

    with pytest.raises(PermissionError, match="tenant"):
        stack["calculation_service"].calculate_kpi(
            stack["owner"],
            calculation_request()
        )


def test_cross_tenant_validation_event_retrieval_filtered(tmp_path):
    stack = create_source_stack(tmp_path)
    stack["validation_repository"].append(
        context(),
        validation_result()
    )

    assert stack["validation_repository"].list_events(
        context(tenant_id="tenant-2")
    ) == []
    assert stack["validation_repository"].list_events_for_source(
        context(tenant_id="tenant-2"),
        "source-1"
    ) == []


def test_cross_tenant_audit_retrieval_filtered(tmp_path):
    stack = create_source_stack(tmp_path)
    stack["audit_service"].record(
        context(),
        action="SOURCE_VALIDATED",
        entity_type="operational_source",
        entity_id="source-1",
    )

    assert stack["audit_repository"].list_events(
        context(tenant_id="tenant-2")
    ) == []


def test_unauthorized_source_registration_rejected(tmp_path):
    stack = create_source_stack(tmp_path)

    with pytest.raises(PermissionError, match="register_source_type"):
        stack["registry_service"].register_source_type(
            context(GovernanceRole.KPI_OWNER),
            source_entry(source_type=OperationalSourceType.QA)
        )


def test_unauthorized_source_validation_rejected(tmp_path):
    stack = create_source_stack(tmp_path)

    with pytest.raises(PermissionError, match="validate_operational_source"):
        stack["validation_service"].validate_source(
            context(GovernanceRole.KPI_OWNER),
            source_record()
        )


def test_unauthorized_source_view_rejected(tmp_path):
    stack = create_source_stack(tmp_path)

    with pytest.raises(PermissionError, match="view_operational_source"):
        stack["registry_service"].get_source_type(
            context(GovernanceRole.KPI_OWNER),
            "survey"
        )


def test_unauthorized_source_usage_writes_access_denied(tmp_path):
    stack = create_source_stack(tmp_path)

    with pytest.raises(PermissionError, match="calculate_kpi"):
        stack["eligibility_service"].confirm_source_eligibility(
            context(GovernanceRole.KPI_STEWARD),
            source_records=[source_record()]
        )

    assert "SOURCE_ACCESS_DENIED" in [
        event.action
        for event in stack["audit_repository"].list_events(context())
    ]


def test_audit_metadata_excludes_raw_comments_pii_payloads_and_secrets(tmp_path):
    stack = create_source_stack(tmp_path)

    stack["audit_service"].record(
        context(),
        action="SOURCE_VALIDATED",
        entity_type="operational_source",
        entity_id="source-1",
        metadata={
            "source_type": "survey",
            "raw_customer_comments": "upset about policy",
            "customer_email": "customer@example.com",
            "employee_name": "Agent One",
            "full_payload": {"csat": 1},
            "auth_token": "secret-token",
            "api_key": "secret-key",
        },
    )
    event = stack["audit_repository"].list_events(context())[-1]

    assert event.metadata == {
        "source_type": "survey",
    }
