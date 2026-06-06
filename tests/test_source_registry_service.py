import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceType,
    SourceRegistryEntry,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.source_registry_service import SourceRegistryService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_source_registry_repository import (
    SQLiteSourceRegistryRepository,
)


def context(role=GovernanceRole.GOVERNANCE_ADMIN, tenant_id="tenant-1"):
    role_value = getattr(role, "value", role)

    return TenantContext(
        tenant_id=tenant_id,
        user_id="admin-1",
        roles={role_value} if role_value else set(),
    )


def registry_entry(
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
        created_by="admin-1",
    )


def create_service(tmp_path):
    database = DatabaseService(tmp_path / "sources.db")
    database.initialize()
    registry_repository = SQLiteSourceRegistryRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)

    return {
        "audit_repository": audit_repository,
        "service": SourceRegistryService(
            registry_repository,
            KPIAuditService(audit_repository)
        ),
    }


def test_register_source_type_persists_entry_and_audit_event(tmp_path):
    services = create_service(tmp_path)

    entry = services["service"].register_source_type(
        context(),
        registry_entry()
    )
    persisted = services["service"].get_source_type(
        context(),
        "survey"
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert entry.source_type == OperationalSourceType.SURVEY
    assert persisted is not None
    assert persisted.source_owner == "owner-1"
    assert "SOURCE_REGISTERED" in actions


def test_register_source_type_requires_governance_admin_permission(tmp_path):
    services = create_service(tmp_path)

    with pytest.raises(PermissionError, match="register_source_type"):
        services["service"].register_source_type(
            context(GovernanceRole.KPI_OWNER),
            registry_entry()
        )


def test_get_source_type_requires_view_permission(tmp_path):
    services = create_service(tmp_path)
    services["service"].register_source_type(
        context(),
        registry_entry()
    )

    with pytest.raises(PermissionError, match="view_operational_source"):
        services["service"].get_source_type(
            context(None),
            "survey"
        )


def test_register_source_type_rejects_duplicate_active_type(tmp_path):
    services = create_service(tmp_path)
    services["service"].register_source_type(
        context(),
        registry_entry()
    )

    with pytest.raises(ValueError, match="Active source type already registered"):
        services["service"].register_source_type(
            context(),
            registry_entry()
        )


def test_register_source_type_rejects_tenant_mismatch(tmp_path):
    services = create_service(tmp_path)

    with pytest.raises(PermissionError, match="tenant"):
        services["service"].register_source_type(
            context(tenant_id="tenant-1"),
            registry_entry("tenant-2")
        )


def test_require_active_source_type_rejects_missing_or_inactive(tmp_path):
    services = create_service(tmp_path)

    with pytest.raises(ValueError, match="Unsupported source type"):
        services["service"].require_active_source_type(
            context(),
            "survey"
        )

    services["service"].register_source_type(
        context(),
        registry_entry(is_active=False)
    )

    with pytest.raises(ValueError, match="inactive"):
        services["service"].require_active_source_type(
            context(),
            "survey"
        )


def test_list_source_types_is_tenant_scoped(tmp_path):
    services = create_service(tmp_path)
    services["service"].register_source_type(
        context(),
        registry_entry()
    )

    assert len(services["service"].list_source_types(context(tenant_id="tenant-1"))) == 1
    assert services["service"].list_source_types(
        context(tenant_id="tenant-2")
    ) == []
