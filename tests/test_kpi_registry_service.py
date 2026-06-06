from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import FormulaStatus, KPIDomain, KPILifecycle
from app.services.database_service import DatabaseService
from app.services.formula_version_service import FormulaConflictError
from app.services.kpi_audit_service import KPIAuditService
from app.services.kpi_registry_service import KPIRegistryService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)


def create_service(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    definition_repository = SQLiteKPIDefinitionRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)

    return KPIRegistryService(
        definition_repository,
        KPIAuditService(audit_repository)
    )


def owner_context():
    return TenantContext(
        tenant_id="tenant-1",
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )


def approver_context():
    return TenantContext(
        tenant_id="tenant-1",
        user_id="approver-1",
        roles={GovernanceRole.KPI_APPROVER.value},
    )


def test_registry_registers_kpi_and_records_audit_event(tmp_path):
    service = create_service(tmp_path)

    definition = service.register_kpi(
        owner_context(),
        kpi_id="csat",
        name="CSAT",
        domain=KPIDomain.CUSTOMER_EXPERIENCE,
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    persisted = service.get_kpi(
        owner_context(),
        "csat"
    )

    assert definition.lifecycle == KPILifecycle.DRAFT
    assert persisted is not None
    assert persisted.owner_user_id == "owner-1"
    assert persisted.steward_user_id == "steward-1"


def test_registry_adds_threshold_with_audit_event(tmp_path):
    service = create_service(tmp_path)
    service.register_kpi(
        owner_context(),
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )

    threshold = service.add_threshold(
        owner_context(),
        kpi_id="csat",
        name="Critical DSAT",
        risk_level="critical",
        minimum=0,
        maximum=79,
    )
    persisted = service.get_kpi(
        owner_context(),
        "csat"
    )

    assert threshold.risk_level == "critical"
    assert persisted is not None
    assert persisted.thresholds[0].name == "Critical DSAT"


def test_registry_formula_requires_separate_approver(tmp_path):
    service = create_service(tmp_path)
    service.register_kpi(
        owner_context(),
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    formula = service.submit_formula_version(
        owner_context(),
        kpi_id="csat",
        version="1.0",
        expression="average_survey_score",
    )

    with pytest.raises(PermissionError, match="Creator cannot approve own formula"):
        service.approve_formula_version(
            owner_context(),
            formula.formula_version_id
        )

    approved = service.approve_formula_version(
        approver_context(),
        formula.formula_version_id
    )

    assert approved.status == FormulaStatus.APPROVED
    assert approved.approved_by == "approver-1"


def test_registry_rejects_overlapping_approved_formula_periods(tmp_path):
    service = create_service(tmp_path)
    service.register_kpi(
        owner_context(),
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    first = service.submit_formula_version(
        owner_context(),
        kpi_id="csat",
        version="1.0",
        expression="count_records",
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 6, 30),
    )
    overlapping = service.submit_formula_version(
        owner_context(),
        kpi_id="csat",
        version="2.0",
        expression="count_records",
        effective_from=datetime(2026, 6, 1),
        effective_to=datetime(2026, 12, 31),
    )

    service.approve_formula_version(
        approver_context(),
        first.formula_version_id
    )

    with pytest.raises(FormulaConflictError, match="overlaps"):
        service.approve_formula_version(
            approver_context(),
            overlapping.formula_version_id
        )


def test_registry_allows_non_overlapping_approved_formula_periods(tmp_path):
    service = create_service(tmp_path)
    service.register_kpi(
        owner_context(),
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    first = service.submit_formula_version(
        owner_context(),
        kpi_id="csat",
        version="1.0",
        expression="count_records",
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 6, 30),
    )
    second = service.submit_formula_version(
        owner_context(),
        kpi_id="csat",
        version="2.0",
        expression="count_records",
        effective_from=datetime(2026, 7, 1),
        effective_to=datetime(2026, 12, 31),
    )

    service.approve_formula_version(
        approver_context(),
        first.formula_version_id
    )
    approved = service.approve_formula_version(
        approver_context(),
        second.formula_version_id
    )

    assert approved.status == FormulaStatus.APPROVED


def test_registry_lifecycle_change_requires_approver_role(tmp_path):
    service = create_service(tmp_path)
    service.register_kpi(
        owner_context(),
        kpi_id="csat",
        name="CSAT",
        domain="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )

    definition = service.change_lifecycle(
        approver_context(),
        kpi_id="csat",
        lifecycle=KPILifecycle.ACTIVE,
    )

    assert definition.lifecycle == KPILifecycle.ACTIVE
