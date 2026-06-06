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
    SourceValidationResult,
    SourceValidationStatus,
)
from app.services.database_service import DatabaseService
from app.services.sqlite_operational_source_repository import (
    SQLiteOperationalSourceRepository,
)
from app.services.sqlite_source_registry_repository import (
    SQLiteSourceRegistryRepository,
)
from app.services.sqlite_source_validation_repository import (
    SQLiteSourceValidationRepository,
)


def context(tenant_id="tenant-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="admin-1",
        roles={GovernanceRole.GOVERNANCE_ADMIN.value},
    )


def registry_entry(tenant_id="tenant-1", source_type="survey"):
    return SourceRegistryEntry(
        tenant_id=tenant_id,
        source_type=source_type,
        source_name="Survey",
        source_owner="owner-1",
        source_steward="steward-1",
        allowed_entity_scopes=[OperationalEntityScope.AGENT],
        required_fields=["csat"],
        numeric_fields=["csat"],
        freshness_threshold_hours=24,
        created_by="admin-1",
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


def create_repositories(tmp_path):
    database = DatabaseService(tmp_path / "sources.db")
    database.initialize()

    return {
        "registry": SQLiteSourceRegistryRepository(database),
        "sources": SQLiteOperationalSourceRepository(database),
        "validations": SQLiteSourceValidationRepository(database),
    }


def test_source_registry_repository_is_tenant_scoped(tmp_path):
    repositories = create_repositories(tmp_path)
    repositories["registry"].upsert_entry(
        context("tenant-1"),
        registry_entry("tenant-1")
    )

    assert repositories["registry"].get_entry(context("tenant-1"), "survey")
    assert repositories["registry"].get_entry(context("tenant-2"), "survey") is None
    assert repositories["registry"].list_entries(context("tenant-2")) == []


def test_source_registry_rejects_cross_tenant_write(tmp_path):
    repositories = create_repositories(tmp_path)

    with pytest.raises(PermissionError, match="tenant-scoped"):
        repositories["registry"].upsert_entry(
            context("tenant-1"),
            registry_entry("tenant-2")
        )


def test_source_registry_rejects_duplicate_active_source_type(tmp_path):
    repositories = create_repositories(tmp_path)
    repositories["registry"].upsert_entry(
        context(),
        registry_entry()
    )

    with pytest.raises(ValueError, match="Active source type already registered"):
        repositories["registry"].upsert_entry(
            context(),
            registry_entry()
        )


def test_operational_source_repository_is_tenant_scoped(tmp_path):
    repositories = create_repositories(tmp_path)
    repositories["sources"].save(
        context("tenant-1"),
        source_record("tenant-1")
    )

    assert repositories["sources"].get_record(context("tenant-1"), "source-1")
    assert repositories["sources"].get_record(context("tenant-2"), "source-1") is None
    assert repositories["sources"].list_records_by_source_type(
        context("tenant-2"),
        "survey"
    ) == []


def test_operational_source_repository_rejects_cross_tenant_write(tmp_path):
    repositories = create_repositories(tmp_path)

    with pytest.raises(PermissionError, match="tenant-scoped"):
        repositories["sources"].save(
            context("tenant-1"),
            source_record("tenant-2")
        )


def test_operational_source_repository_detects_duplicate_source(tmp_path):
    repositories = create_repositories(tmp_path)
    repositories["sources"].save(
        context(),
        source_record(source_record_id="source-1")
    )
    duplicate = source_record(source_record_id="source-2")

    assert repositories["sources"].find_duplicate(
        context(),
        duplicate
    ).source_record_id == "source-1"


def test_source_validation_repository_is_tenant_scoped(tmp_path):
    repositories = create_repositories(tmp_path)
    validation = SourceValidationResult(
        tenant_id="tenant-1",
        source_record_id="source-1",
        source_type="survey",
        validation_status="valid",
        data_quality_status="valid",
    )

    repositories["validations"].append(
        context("tenant-1"),
        validation
    )

    assert len(repositories["validations"].list_events(context("tenant-1"))) == 1
    assert repositories["validations"].list_events(context("tenant-2")) == []
    assert repositories["validations"].list_events_for_source(
        context("tenant-2"),
        "source-1"
    ) == []


def test_source_validation_repository_rejects_cross_tenant_write(tmp_path):
    repositories = create_repositories(tmp_path)
    validation = SourceValidationResult(
        tenant_id="tenant-2",
        source_record_id="source-1",
        source_type="survey",
        validation_status="valid",
        data_quality_status="valid",
    )

    with pytest.raises(PermissionError, match="tenant-scoped"):
        repositories["validations"].append(
            context("tenant-1"),
            validation
        )
