import json
from datetime import datetime
from typing import Any

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.operational_source import (
    OperationalSourceType,
    SourceQualityStatus,
    SourceValidationResult,
    SourceValidationStatus,
)


class SQLiteSourceValidationRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def append(
        self,
        context: TenantContext | None,
        validation_result: SourceValidationResult
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, validation_result.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO source_validation_events (
                    tenant_id,
                    validation_event_id,
                    source_record_id,
                    source_type,
                    validation_status,
                    data_quality_status,
                    quality_issues_json,
                    message,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                validation_result.tenant_id,
                validation_result.validation_event_id,
                validation_result.source_record_id,
                validation_result.source_type.value,
                validation_result.validation_status.value,
                validation_result.data_quality_status.value,
                json.dumps(validation_result.quality_issues),
                validation_result.message,
                validation_result.created_at.isoformat(),
                json.dumps(validation_result.metadata),
            ))
            conn.commit()

    def list_events_for_source(
        self,
        context: TenantContext | None,
        source_record_id: str
    ) -> list[SourceValidationResult]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    validation_event_id,
                    source_record_id,
                    source_type,
                    validation_status,
                    data_quality_status,
                    quality_issues_json,
                    message,
                    created_at,
                    metadata_json
                FROM source_validation_events
                WHERE tenant_id = ?
                  AND source_record_id = ?
                ORDER BY created_at
            """, (
                context.tenant_id,
                source_record_id,
            ))
            rows = cursor.fetchall()

        return [
            self._result_from_row(row)
            for row in rows
        ]

    def list_events(
        self,
        context: TenantContext | None
    ) -> list[SourceValidationResult]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    validation_event_id,
                    source_record_id,
                    source_type,
                    validation_status,
                    data_quality_status,
                    quality_issues_json,
                    message,
                    created_at,
                    metadata_json
                FROM source_validation_events
                WHERE tenant_id = ?
                ORDER BY created_at
            """, (
                context.tenant_id,
            ))
            rows = cursor.fetchall()

        return [
            self._result_from_row(row)
            for row in rows
        ]

    def _result_from_row(self, row: tuple[Any, ...]) -> SourceValidationResult:
        return SourceValidationResult(
            tenant_id=row[0],
            validation_event_id=row[1],
            source_record_id=row[2],
            source_type=OperationalSourceType.from_value(row[3]),
            validation_status=SourceValidationStatus.from_value(row[4]),
            data_quality_status=SourceQualityStatus.from_value(row[5]),
            quality_issues=json.loads(row[6] or "[]"),
            message=row[7] or "",
            created_at=datetime.fromisoformat(row[8]),
            metadata=json.loads(row[9] or "{}"),
        )

    def _require_same_tenant(
        self,
        context: TenantContext,
        tenant_id: str
    ) -> None:
        if context.tenant_id != tenant_id:
            raise PermissionError("Repository access must be tenant-scoped.")
