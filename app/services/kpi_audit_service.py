from typing import Any

from app.core.audit import AuditEvent
from app.core.tenant_context import TenantContext, require_tenant_context


class KPIAuditService:
    def __init__(self, audit_repository):
        self.audit_repository = audit_repository

    def record(
        self,
        context: TenantContext | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None
    ) -> AuditEvent:
        context = require_tenant_context(context)
        event = AuditEvent(
            action=action,
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )

        self.audit_repository.append(
            context,
            event
        )

        return event

    def list_events(
        self,
        context: TenantContext | None,
        entity_type: str | None = None,
        entity_id: str | None = None
    ) -> list[AuditEvent]:
        context = require_tenant_context(context)

        return self.audit_repository.list_events(
            context,
            entity_type=entity_type,
            entity_id=entity_id
        )
