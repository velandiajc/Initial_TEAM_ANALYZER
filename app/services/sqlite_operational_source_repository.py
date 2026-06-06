import json
from datetime import datetime
from typing import Any

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceRecord,
    OperationalSourceType,
    SourceQualityStatus,
    SourceValidationStatus,
)


class SQLiteOperationalSourceRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(
        self,
        context: TenantContext | None,
        source_record: OperationalSourceRecord
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, source_record.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO operational_sources (
                    tenant_id,
                    source_record_id,
                    source_type,
                    source_reference,
                    source_version,
                    lineage_id,
                    period_start,
                    period_end,
                    entity_type,
                    entity_id,
                    validation_status,
                    data_quality_status,
                    metric_values_json,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source_record.tenant_id,
                source_record.source_record_id,
                source_record.source_type.value,
                source_record.source_reference,
                source_record.source_version,
                source_record.lineage_id,
                _dt_to_text(source_record.period_start),
                _dt_to_text(source_record.period_end),
                source_record.entity_type.value,
                source_record.entity_id,
                source_record.validation_status.value,
                source_record.data_quality_status.value,
                json.dumps(source_record.metric_values),
                source_record.created_at.isoformat(),
                json.dumps(source_record.metadata),
            ))
            conn.commit()

    def get_record(
        self,
        context: TenantContext | None,
        source_record_id: str
    ) -> OperationalSourceRecord | None:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    source_record_id,
                    source_type,
                    source_reference,
                    source_version,
                    lineage_id,
                    period_start,
                    period_end,
                    entity_type,
                    entity_id,
                    validation_status,
                    data_quality_status,
                    metric_values_json,
                    created_at,
                    metadata_json
                FROM operational_sources
                WHERE tenant_id = ?
                  AND source_record_id = ?
            """, (
                context.tenant_id,
                source_record_id,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._record_from_row(row)

    def list_records_by_source_type(
        self,
        context: TenantContext | None,
        source_type: OperationalSourceType | str
    ) -> list[OperationalSourceRecord]:
        context = require_tenant_context(context)
        source_type = OperationalSourceType.from_value(source_type)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    source_record_id,
                    source_type,
                    source_reference,
                    source_version,
                    lineage_id,
                    period_start,
                    period_end,
                    entity_type,
                    entity_id,
                    validation_status,
                    data_quality_status,
                    metric_values_json,
                    created_at,
                    metadata_json
                FROM operational_sources
                WHERE tenant_id = ?
                  AND source_type = ?
                ORDER BY created_at
            """, (
                context.tenant_id,
                source_type.value,
            ))
            rows = cursor.fetchall()

        return [
            self._record_from_row(row)
            for row in rows
        ]

    def get_records_by_source_reference(
        self,
        context: TenantContext | None,
        source_reference: str
    ) -> list[OperationalSourceRecord]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    source_record_id,
                    source_type,
                    source_reference,
                    source_version,
                    lineage_id,
                    period_start,
                    period_end,
                    entity_type,
                    entity_id,
                    validation_status,
                    data_quality_status,
                    metric_values_json,
                    created_at,
                    metadata_json
                FROM operational_sources
                WHERE tenant_id = ?
                  AND source_reference = ?
                ORDER BY created_at
            """, (
                context.tenant_id,
                source_reference,
            ))
            rows = cursor.fetchall()

        return [
            self._record_from_row(row)
            for row in rows
        ]

    def find_duplicate(
        self,
        context: TenantContext | None,
        source_record: OperationalSourceRecord
    ) -> OperationalSourceRecord | None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, source_record.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    source_record_id,
                    source_type,
                    source_reference,
                    source_version,
                    lineage_id,
                    period_start,
                    period_end,
                    entity_type,
                    entity_id,
                    validation_status,
                    data_quality_status,
                    metric_values_json,
                    created_at,
                    metadata_json
                FROM operational_sources
                WHERE tenant_id = ?
                  AND source_type = ?
                  AND entity_type = ?
                  AND COALESCE(entity_id, '') = COALESCE(?, '')
                  AND COALESCE(period_start, '') = COALESCE(?, '')
                  AND COALESCE(period_end, '') = COALESCE(?, '')
                  AND COALESCE(source_reference, '') = COALESCE(?, '')
                  AND source_record_id != ?
                LIMIT 1
            """, (
                context.tenant_id,
                source_record.source_type.value,
                source_record.entity_type.value,
                source_record.entity_id,
                _dt_to_text(source_record.period_start),
                _dt_to_text(source_record.period_end),
                source_record.source_reference,
                source_record.source_record_id,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._record_from_row(row)

    def _record_from_row(self, row: tuple[Any, ...]) -> OperationalSourceRecord:
        return OperationalSourceRecord(
            tenant_id=row[0],
            source_record_id=row[1],
            source_type=OperationalSourceType.from_value(row[2]),
            source_reference=row[3] or "",
            source_version=row[4],
            lineage_id=row[5],
            period_start=_text_to_dt(row[6]) if row[6] else None,
            period_end=_text_to_dt(row[7]) if row[7] else None,
            entity_type=OperationalEntityScope.from_value(row[8]),
            entity_id=row[9] or "",
            validation_status=SourceValidationStatus.from_value(row[10]),
            data_quality_status=SourceQualityStatus.from_value(row[11]),
            metric_values=json.loads(row[12] or "{}"),
            created_at=_text_to_dt(row[13]),
            metadata=json.loads(row[14] or "{}"),
        )

    def _require_same_tenant(
        self,
        context: TenantContext,
        tenant_id: str
    ) -> None:
        if context.tenant_id != tenant_id:
            raise PermissionError("Repository access must be tenant-scoped.")


def _dt_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _text_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)
