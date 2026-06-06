from datetime import datetime

import pytest

from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceRecord,
    OperationalSourceType,
    SourceQualityDimension,
    SourceQualityStatus,
    SourceRegistryEntry,
    SourceValidationResult,
    SourceValidationStatus,
    source_quality_issue,
)


def test_registry_entry_requires_owner_and_steward():
    with pytest.raises(ValueError, match="source_owner is required"):
        SourceRegistryEntry(
            tenant_id="tenant-1",
            source_type=OperationalSourceType.SURVEY,
            source_name="Survey",
            source_owner="",
            source_steward="steward-1",
        )

    with pytest.raises(ValueError, match="source_steward is required"):
        SourceRegistryEntry(
            tenant_id="tenant-1",
            source_type=OperationalSourceType.SURVEY,
            source_name="Survey",
            source_owner="owner-1",
            source_steward="",
        )


def test_operational_source_record_requires_version_and_lineage():
    with pytest.raises(ValueError, match="source_version is required"):
        OperationalSourceRecord(
            tenant_id="tenant-1",
            source_type="survey",
            source_reference="survey:2026-03",
            source_version="",
            lineage_id="lineage-1",
            period_start=datetime(2026, 3, 1),
            period_end=datetime(2026, 3, 31),
        )

    with pytest.raises(ValueError, match="lineage_id is required"):
        OperationalSourceRecord(
            tenant_id="tenant-1",
            source_type="survey",
            source_reference="survey:2026-03",
            source_version="v1",
            lineage_id="",
            period_start=datetime(2026, 3, 1),
            period_end=datetime(2026, 3, 31),
        )


def test_source_validation_and_quality_status_are_separate():
    record = OperationalSourceRecord(
        tenant_id="tenant-1",
        source_type="survey",
        source_reference="survey:2026-03",
        source_version="v1",
        lineage_id="lineage-1",
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        validation_status="warning",
        data_quality_status="stale_source",
    )

    assert record.validation_status == SourceValidationStatus.WARNING
    assert record.data_quality_status == SourceQualityStatus.STALE_SOURCE


def test_quality_issue_requires_allowed_dimension():
    result = SourceValidationResult(
        tenant_id="tenant-1",
        source_record_id="source-1",
        source_type="survey",
        validation_status="invalid",
        data_quality_status="missing_required_field",
        quality_issues=[
            source_quality_issue(
                SourceQualityDimension.COMPLETENESS,
                SourceQualityStatus.MISSING_REQUIRED_FIELD,
                field_name="csat",
            )
        ],
    )

    assert result.quality_issues[0]["dimension"] == "completeness"

    with pytest.raises(ValueError, match="Unsupported source quality dimension"):
        SourceValidationResult(
            tenant_id="tenant-1",
            source_record_id="source-1",
            source_type="survey",
            validation_status="invalid",
            data_quality_status="missing_required_field",
            quality_issues=[
                {
                    "dimension": "not-real",
                    "code": "missing_required_field",
                }
            ],
        )


def test_source_values_normalize_from_strings():
    entry = SourceRegistryEntry(
        tenant_id="tenant-1",
        source_type="Survey",
        source_name="Survey",
        source_owner="owner-1",
        source_steward="steward-1",
        allowed_entity_scopes=["Agent", OperationalEntityScope.TEAM],
        required_fields=[" csat ", ""],
    )

    assert entry.source_type == OperationalSourceType.SURVEY
    assert entry.allowed_entity_scopes == [
        OperationalEntityScope.AGENT,
        OperationalEntityScope.TEAM,
    ]
    assert entry.required_fields == ["csat"]
