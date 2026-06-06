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
            metadata=sanitize_audit_metadata(metadata or {}),
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


SENSITIVE_METADATA_KEY_PARTS = [
    "api_key",
    "auth",
    "comment",
    "customer_email",
    "customer_name",
    "customer_phone",
    "employee_email",
    "employee_name",
    "employee_phone",
    "full_payload",
    "password",
    "payload",
    "raw",
    "secret",
    "ssn",
    "token",
]


def sanitize_audit_metadata(value):
    if isinstance(value, dict):
        sanitized = {}

        for key, item in value.items():
            if _is_sensitive_key(key):
                continue

            sanitized[key] = sanitize_audit_metadata(item)

        return sanitized

    if isinstance(value, list):
        return [
            sanitize_audit_metadata(item)
            for item in value
        ]

    return value


def _is_sensitive_key(key) -> bool:
    normalized = str(key).strip().lower()

    return any(
        part in normalized
        for part in SENSITIVE_METADATA_KEY_PARTS
    )
