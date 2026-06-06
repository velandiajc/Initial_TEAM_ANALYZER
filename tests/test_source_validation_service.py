from datetime import datetime, timedelta, timezone

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import utc_now
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
from app.services.source_validation_service import SourceValidationService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
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
        user_id="admin-1",
        roles={role_value} if role_value else set(),
    )


def registry_entry(
    source_type=OperationalSourceType.SURVEY,
    is_active=True,
    freshness_threshold_hours=None
):
    return SourceRegistryEntry(
        tenant_id="tenant-1",
        source_type=source_type,
        source_name="Survey",
        source_owner="owner-1",
        source_steward="steward-1",
        allowed_entity_scopes=[OperationalEntityScope.AGENT],
        required_fields=["csat", "survey_count"],
        numeric_fields=["csat", "survey_count"],
        freshness_threshold_hours=freshness_threshold_hours,
        is_active=is_active,
        created_by="admin-1",
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
        "metric_values": {
            "csat": 92,
            "survey_count": 12,
        },
    }
    values.update(overrides)

    return OperationalSourceRecord(**values)


def create_services(tmp_path, entry=None):
    database = DatabaseService(tmp_path / "sources.db")
    database.initialize()
    registry_repository = SQLiteSourceRegistryRepository(database)
    source_repository = SQLiteOperationalSourceRepository(database)
    validation_repository = SQLiteSourceValidationRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)

    if entry is not None:
        registry_repository.upsert_entry(
            context(),
            entry
        )

    return {
        "audit_repository": audit_repository,
        "source_repository": source_repository,
        "validation_repository": validation_repository,
        "service": SourceValidationService(
            registry_repository,
            source_repository,
            validation_repository,
            KPIAuditService(audit_repository)
        ),
    }


def test_valid_source_is_persisted_with_validation_event_and_audit(tmp_path):
    services = create_services(tmp_path, registry_entry())

    result = services["service"].validate_source(
        context(),
        source_record()
    )

    assert result.validation_status == SourceValidationStatus.VALID
    assert result.data_quality_status == SourceQualityStatus.VALID
    assert services["source_repository"].get_record(context(), "source-1")
    assert len(services["validation_repository"].list_events(context())) == 1
    assert "SOURCE_VALIDATED" in [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]


def test_missing_required_metric_invalidates_source(tmp_path):
    services = create_services(tmp_path, registry_entry())

    result = services["service"].validate_source(
        context(),
        source_record(metric_values={"csat": 92})
    )

    assert result.validation_status == SourceValidationStatus.INVALID
    assert result.data_quality_status == SourceQualityStatus.MISSING_REQUIRED_FIELD
    assert result.quality_issues[0]["dimension"] == "completeness"
    assert services["source_repository"].get_record(context(), "source-1") is None


def test_invalid_period_invalidates_source(tmp_path):
    services = create_services(tmp_path, registry_entry())

    result = services["service"].validate_source(
        context(),
        source_record(
            period_start=datetime(2026, 4, 1),
            period_end=datetime(2026, 3, 1),
        )
    )

    assert result.validation_status == SourceValidationStatus.INVALID
    assert result.data_quality_status == SourceQualityStatus.INVALID_PERIOD


def test_invalid_entity_scope_and_missing_entity_id_are_classified(tmp_path):
    services = create_services(tmp_path, registry_entry())

    result = services["service"].validate_source(
        context(),
        source_record(
            entity_type=OperationalEntityScope.TEAM,
            entity_id="",
        )
    )
    codes = {
        issue["code"]
        for issue in result.quality_issues
    }

    assert result.validation_status == SourceValidationStatus.INVALID
    assert "invalid_entity_scope" in codes
    assert "missing_required_field" in codes


def test_invalid_numeric_and_percentage_values_are_classified(tmp_path):
    services = create_services(tmp_path, registry_entry())

    result = services["service"].validate_source(
        context(),
        source_record(
            metric_values={
                "csat": 101,
                "survey_count": -1,
            }
        )
    )

    assert result.validation_status == SourceValidationStatus.INVALID
    assert result.data_quality_status == SourceQualityStatus.INVALID_METRIC_VALUE


def test_stale_source_returns_warning(tmp_path):
    services = create_services(
        tmp_path,
        registry_entry(freshness_threshold_hours=1)
    )

    result = services["service"].validate_source(
        context(),
        source_record(
            period_start=utc_now() - timedelta(hours=3),
            period_end=utc_now() - timedelta(hours=2),
        )
    )

    assert result.validation_status == SourceValidationStatus.WARNING
    assert result.data_quality_status == SourceQualityStatus.STALE_SOURCE
    assert services["source_repository"].get_record(context(), "source-1")


def test_duplicate_source_is_invalidated(tmp_path):
    services = create_services(tmp_path, registry_entry())
    services["service"].validate_source(
        context(),
        source_record(source_record_id="source-1")
    )

    result = services["service"].validate_source(
        context(),
        source_record(source_record_id="source-2")
    )

    assert result.validation_status == SourceValidationStatus.INVALID
    assert result.data_quality_status == SourceQualityStatus.DUPLICATE_SOURCE


def test_unsupported_source_type_invalidates_source(tmp_path):
    services = create_services(tmp_path)

    result = services["service"].validate_source(
        context(),
        source_record(source_type=OperationalSourceType.QA)
    )

    assert result.validation_status == SourceValidationStatus.INVALID
    assert result.data_quality_status == SourceQualityStatus.UNSUPPORTED_SOURCE_TYPE


def test_inactive_source_type_invalidates_source(tmp_path):
    services = create_services(tmp_path, registry_entry(is_active=False))

    result = services["service"].validate_source(
        context(),
        source_record()
    )

    assert result.validation_status == SourceValidationStatus.INVALID
    assert result.data_quality_status == SourceQualityStatus.UNSUPPORTED_SOURCE_TYPE


def test_cross_tenant_source_validation_is_rejected_and_audited(tmp_path):
    services = create_services(tmp_path, registry_entry())

    with pytest.raises(PermissionError, match="tenant"):
        services["service"].validate_source(
            context("governance_admin", "tenant-1"),
            source_record(tenant_id="tenant-2")
        )

    events = services["audit_repository"].list_events(context())
    assert events[-1].action == "SOURCE_REJECTED"


def test_unauthorized_source_validation_is_rejected_and_audited(tmp_path):
    services = create_services(tmp_path, registry_entry())

    with pytest.raises(PermissionError, match="validate_operational_source"):
        services["service"].validate_source(
            context(GovernanceRole.KPI_OWNER),
            source_record()
        )

    assert "SOURCE_VALIDATION_FAILED" in [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
