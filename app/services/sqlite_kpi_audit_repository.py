import json
from datetime import datetime
from typing import Any

from app.core.audit import AuditEvent
from app.core.tenant_context import TenantContext, require_tenant_context


class SQLiteKPIAuditRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def append(
        self,
        context: TenantContext | None,
        event: AuditEvent
    ) -> None:
        context = require_tenant_context(context)

        if context.tenant_id != event.tenant_id:
            raise PermissionError("Audit event tenant does not match context.")

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO kpi_audit_events (
                    tenant_id,
                    event_id,
                    action,
                    actor_user_id,
                    entity_type,
                    entity_id,
                    occurred_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.tenant_id,
                event.event_id,
                event.action,
                event.actor_user_id,
                event.entity_type,
                event.entity_id,
                event.occurred_at.isoformat(),
                json.dumps(event.metadata),
            ))
            conn.commit()

    def list_events(
        self,
        context: TenantContext | None,
        entity_type: str | None = None,
        entity_id: str | None = None
    ) -> list[AuditEvent]:
        context = require_tenant_context(context)
        query = """
            SELECT
                action,
                tenant_id,
                actor_user_id,
                entity_type,
                entity_id,
                event_id,
                occurred_at,
                metadata_json
            FROM kpi_audit_events
            WHERE tenant_id = ?
        """
        params: list[Any] = [
            context.tenant_id,
        ]

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)

        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)

        query += " ORDER BY occurred_at"

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [
            AuditEvent(
                action=row[0],
                tenant_id=row[1],
                actor_user_id=row[2],
                entity_type=row[3],
                entity_id=row[4],
                event_id=row[5],
                occurred_at=datetime.fromisoformat(row[6]),
                metadata=json.loads(row[7] or "{}"),
            )
            for row in rows
        ]
