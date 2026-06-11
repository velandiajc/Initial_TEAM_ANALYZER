from app.core.permissions import RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.domain.performance.value_objects import CoachingAuditEvent


class PerformanceServiceSupport:
    def __init__(self, audit_service, rbac_service: RBACService | None = None):
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def context(self, context: TenantContext | None) -> TenantContext:
        return require_tenant_context(context)

    def require_permission(self, context, permission, entity_type, entity_id):
        try:
            self.rbac_service.require_permission(context, permission)
        except PermissionError as exc:
            self.audit(
                context,
                CoachingAuditEvent.COACHING_ACCESS_DENIED,
                entity_type,
                entity_id,
                {"reason": str(exc)},
            )
            raise

    def require_entity(self, context, entity, entity_type, entity_id):
        if entity is not None:
            return entity
        self.audit(
            context,
            CoachingAuditEvent.COACHING_ACCESS_DENIED,
            entity_type,
            entity_id,
            {"reason": "Record not found or outside tenant scope."},
        )
        raise PermissionError(
            f"{entity_type} not found or outside tenant scope."
        )

    def audit(
        self,
        context,
        action: CoachingAuditEvent | str,
        entity_type: str,
        entity_id: str,
        metadata=None,
    ):
        action_value = getattr(action, "value", action)
        return self.audit_service.record(
            context,
            action=str(action_value),
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )

    def audit_modification_rejected(
        self,
        context,
        entity_type,
        entity_id,
        reason,
    ):
        self.audit(
            context,
            CoachingAuditEvent.COACHING_RECORD_MODIFICATION_REJECTED,
            entity_type,
            entity_id,
            {"reason": str(reason)},
        )
