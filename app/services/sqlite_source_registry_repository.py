import json
from datetime import datetime
from typing import Any

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceType,
    SourceRegistryEntry,
)


class SQLiteSourceRegistryRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def upsert_entry(
        self,
        context: TenantContext | None,
        entry: SourceRegistryEntry
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, entry.tenant_id)

        existing = self.get_entry(
            context,
            entry.source_type
        )

        if existing is not None and existing.is_active and entry.is_active:
            raise ValueError(
                f"Active source type already registered: {entry.source_type.value}"
            )

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO source_registry (
                    tenant_id,
                    source_type,
                    source_name,
                    source_owner,
                    source_steward,
                    allowed_entity_scopes_json,
                    required_fields_json,
                    numeric_fields_json,
                    freshness_threshold_hours,
                    is_active,
                    created_by,
                    created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.tenant_id,
                entry.source_type.value,
                entry.source_name,
                entry.source_owner,
                entry.source_steward,
                json.dumps([
                    scope.value
                    for scope in entry.allowed_entity_scopes
                ]),
                json.dumps(entry.required_fields),
                json.dumps(entry.numeric_fields),
                entry.freshness_threshold_hours,
                1 if entry.is_active else 0,
                entry.created_by,
                entry.created_at.isoformat(),
                json.dumps(entry.metadata),
            ))
            conn.commit()

    def get_entry(
        self,
        context: TenantContext | None,
        source_type: OperationalSourceType | str
    ) -> SourceRegistryEntry | None:
        context = require_tenant_context(context)
        source_type = OperationalSourceType.from_value(source_type)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    source_type,
                    source_name,
                    source_owner,
                    source_steward,
                    allowed_entity_scopes_json,
                    required_fields_json,
                    numeric_fields_json,
                    freshness_threshold_hours,
                    is_active,
                    created_by,
                    created_at,
                    metadata_json
                FROM source_registry
                WHERE tenant_id = ?
                  AND source_type = ?
            """, (
                context.tenant_id,
                source_type.value,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._entry_from_row(row)

    def list_entries(
        self,
        context: TenantContext | None
    ) -> list[SourceRegistryEntry]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    source_type,
                    source_name,
                    source_owner,
                    source_steward,
                    allowed_entity_scopes_json,
                    required_fields_json,
                    numeric_fields_json,
                    freshness_threshold_hours,
                    is_active,
                    created_by,
                    created_at,
                    metadata_json
                FROM source_registry
                WHERE tenant_id = ?
                ORDER BY source_type
            """, (
                context.tenant_id,
            ))
            rows = cursor.fetchall()

        return [
            self._entry_from_row(row)
            for row in rows
        ]

    def _entry_from_row(self, row: tuple[Any, ...]) -> SourceRegistryEntry:
        return SourceRegistryEntry(
            tenant_id=row[0],
            source_type=OperationalSourceType.from_value(row[1]),
            source_name=row[2],
            source_owner=row[3],
            source_steward=row[4],
            allowed_entity_scopes=[
                OperationalEntityScope.from_value(scope)
                for scope in json.loads(row[5] or "[]")
            ],
            required_fields=json.loads(row[6] or "[]"),
            numeric_fields=json.loads(row[7] or "[]"),
            freshness_threshold_hours=row[8],
            is_active=bool(row[9]),
            created_by=row[10] or "",
            created_at=datetime.fromisoformat(row[11]),
            metadata=json.loads(row[12] or "{}"),
        )

    def _require_same_tenant(
        self,
        context: TenantContext,
        tenant_id: str
    ) -> None:
        if context.tenant_id != tenant_id:
            raise PermissionError("Repository access must be tenant-scoped.")
