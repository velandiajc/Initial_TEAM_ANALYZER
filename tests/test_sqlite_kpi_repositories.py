from app.core.audit import AuditEvent
from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import KPIDefinition, KPIDomain
from app.services.database_service import DatabaseService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)


def context(tenant_id="tenant-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )


def test_definition_repository_is_tenant_scoped(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    repository = SQLiteKPIDefinitionRepository(database)
    definition = KPIDefinition(
        kpi_id="csat",
        tenant_id="tenant-1",
        name="CSAT",
        domain=KPIDomain.CUSTOMER_EXPERIENCE,
        owner_user_id="owner-1",
        steward_user_id="steward-1",
        created_by="owner-1",
    )

    repository.upsert_definition(
        context("tenant-1"),
        definition
    )

    assert repository.get_definition(context("tenant-1"), "csat") is not None
    assert repository.get_definition(context("tenant-2"), "csat") is None


def test_definition_repository_rejects_cross_tenant_write(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    repository = SQLiteKPIDefinitionRepository(database)
    definition = KPIDefinition(
        kpi_id="csat",
        tenant_id="tenant-2",
        name="CSAT",
        domain=KPIDomain.CUSTOMER_EXPERIENCE,
        owner_user_id="owner-1",
        steward_user_id="steward-1",
        created_by="owner-1",
    )

    try:
        repository.upsert_definition(context("tenant-1"), definition)
    except PermissionError as exc:
        assert "tenant-scoped" in str(exc)
    else:
        raise AssertionError("Expected cross-tenant write to be rejected.")


def test_audit_repository_is_tenant_scoped(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    repository = SQLiteKPIAuditRepository(database)
    event = AuditEvent(
        action="kpi_definition_registered",
        tenant_id="tenant-1",
        actor_user_id="owner-1",
        entity_type="kpi_definition",
        entity_id="csat",
    )

    repository.append(
        context("tenant-1"),
        event
    )

    assert len(repository.list_events(context("tenant-1"))) == 1
    assert repository.list_events(context("tenant-2")) == []
