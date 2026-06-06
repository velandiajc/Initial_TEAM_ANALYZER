from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceRecord,
    OperationalSourceType,
    SourceQualityStatus,
    SourceRegistryEntry,
    SourceValidationStatus,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.kpi_source_eligibility_service import (
    KPISourceEligibilityError,
    KPISourceEligibilityService,
)
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_operational_source_repository import (
    SQLiteOperationalSourceRepository,
)
from app.services.sqlite_source_registry_repository import (
    SQLiteSourceRegistryRepository,
)


def context(role=GovernanceRole.KPI_OWNER, tenant_id="tenant-1"):
    role_value = getattr(role, "value", role)

    return TenantContext(
        tenant_id=tenant_id,
        user_id="owner-1",
        roles={role_value} if role_value else set(),
    )


def registry_entry(source_type=OperationalSourceType.SURVEY, is_active=True):
    return SourceRegistryEntry(
        tenant_id="tenant-1",
        source_type=source_type,
        source_name="Survey",
        source_owner="owner-1",
        source_steward="steward-1",
        allowed_entity_scopes=[OperationalEntityScope.AGENT],
        is_active=is_active,
    )


def source_record(**overrides):
    values = {
        "tenant_id": "tenant-1",
        "source_record_id": "source-1",
        "source_type": OperationalSourceType.SURVEY,
        "source_reference": "survey:2026-03",
        "source_version": "v1",
        "lineage_id": "lineage-1",
        "period_start": datetime(2026, 3, 1),
        "period_end": datetime(2026, 3, 31),
        "entity_type": OperationalEntityScope.AGENT,
        "entity_id": "agent-1",
        "metric_values": {"csat": 92},
        "validation_status": SourceValidationStatus.VALID,
        "data_quality_status": SourceQualityStatus.VALID,
    }
    values.update(overrides)

    return OperationalSourceRecord(**values)


def create_services(tmp_path, entry=None):
    database = DatabaseService(tmp_path / "sources.db")
    database.initialize()
    registry_repository = SQLiteSourceRegistryRepository(database)
    source_repository = SQLiteOperationalSourceRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)

    registry_repository.upsert_entry(
        context(GovernanceRole.GOVERNANCE_ADMIN),
        entry or registry_entry()
    )

    return {
        "audit_repository": audit_repository,
        "source_repository": source_repository,
        "service": KPISourceEligibilityService(
            registry_repository,
            source_repository,
            KPIAuditService(audit_repository)
        ),
    }


def test_confirm_source_eligibility_returns_metadata_summary_and_audit(tmp_path):
    services = create_services(tmp_path)

    summary = services["service"].confirm_source_eligibility(
        context(),
        source_records=[source_record()]
    )

    assert summary["source_record_ids"] == ["source-1"]
    assert summary["source_references"] == ["survey:2026-03"]
    assert summary["source_types"] == ["survey"]
    assert summary["source_version"] == ["v1"]
    assert summary["lineage_id"] == ["lineage-1"]
    assert summary["source_validation_status"] == ["valid"]
    assert summary["source_quality_summary"] == {"valid": 1}
    assert "SOURCE_USED_FOR_CALCULATION" in [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]


def test_confirm_source_eligibility_resolves_ids_and_references(tmp_path):
    services = create_services(tmp_path)
    services["source_repository"].save(
        context(),
        source_record(source_record_id="source-1")
    )

    by_id = services["service"].confirm_source_eligibility(
        context(),
        source_record_ids=["source-1"]
    )
    by_reference = services["service"].confirm_source_eligibility(
        context(),
        source_references=["survey:2026-03"]
    )

    assert by_id["source_record_ids"] == ["source-1"]
    assert by_reference["source_record_ids"] == ["source-1"]


def test_source_lineage_and_version_are_required(tmp_path):
    services = create_services(tmp_path)
    missing_lineage = source_record()
    missing_lineage.lineage_id = ""
    missing_version = source_record()
    missing_version.source_version = ""

    with pytest.raises(KPISourceEligibilityError, match="lineage"):
        services["service"].confirm_source_eligibility(
            context(),
            source_records=[missing_lineage]
        )

    with pytest.raises(KPISourceEligibilityError, match="version"):
        services["service"].confirm_source_eligibility(
            context(),
            source_records=[missing_version]
        )


def test_failed_or_stale_validation_blocks_source_usage(tmp_path):
    services = create_services(tmp_path)

    with pytest.raises(KPISourceEligibilityError, match="validation failed"):
        services["service"].confirm_source_eligibility(
            context(),
            source_records=[
                source_record(validation_status=SourceValidationStatus.INVALID)
            ]
        )

    with pytest.raises(KPISourceEligibilityError, match="Source quality"):
        services["service"].confirm_source_eligibility(
            context(),
            source_records=[
                source_record(
                    validation_status=SourceValidationStatus.WARNING,
                    data_quality_status=SourceQualityStatus.STALE_SOURCE,
                )
            ]
        )


def test_unsupported_or_inactive_source_type_blocks_usage(tmp_path):
    services = create_services(tmp_path)

    with pytest.raises(KPISourceEligibilityError, match="Unsupported source type"):
        services["service"].confirm_source_eligibility(
            context(),
            source_records=[source_record(source_type=OperationalSourceType.QA)]
        )

    inactive_services = create_services(
        tmp_path / "inactive",
        registry_entry(is_active=False)
    )

    with pytest.raises(KPISourceEligibilityError, match="Inactive source type"):
        inactive_services["service"].confirm_source_eligibility(
            context(),
            source_records=[source_record()]
        )


def test_cross_tenant_source_usage_is_rejected_and_audited(tmp_path):
    services = create_services(tmp_path)

    with pytest.raises(PermissionError, match="tenant"):
        services["service"].confirm_source_eligibility(
            context(),
            source_records=[source_record(tenant_id="tenant-2")]
        )

    events = services["audit_repository"].list_events(context())
    assert events[-1].action == "SOURCE_ACCESS_DENIED"


def test_unauthorized_source_usage_writes_access_denied_audit(tmp_path):
    services = create_services(tmp_path)

    with pytest.raises(PermissionError, match="calculate_kpi"):
        services["service"].confirm_source_eligibility(
            context(GovernanceRole.KPI_STEWARD),
            source_records=[source_record()]
        )

    assert "SOURCE_ACCESS_DENIED" in [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
