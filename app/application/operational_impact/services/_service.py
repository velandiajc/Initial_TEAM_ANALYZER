from app.core.permissions import RBACService
from app.core.tenant_context import require_tenant_context
from app.domain.operational_impact import OperationalImpactAuditEvent


class OperationalImpactServiceSupport:
    def __init__(self, audit_service, rbac_service=None):
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def context(self, context):
        return require_tenant_context(context)

    def require_permission(
        self,
        context,
        permission,
        entity_type,
        entity_id,
        access_denied_event=(
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_ACCESS_DENIED
        ),
    ):
        try:
            self.rbac_service.require_permission(context, permission)
        except PermissionError as exc:
            self.audit(
                context,
                access_denied_event,
                entity_type,
                entity_id,
                {"reason": str(exc)},
            )
            raise

    def require_entity(
        self,
        context,
        entity,
        entity_type,
        entity_id,
        access_denied_event=(
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_ACCESS_DENIED
        ),
    ):
        if entity is not None:
            return entity
        self.audit(
            context,
            access_denied_event,
            entity_type,
            entity_id,
            {"reason": "Record not found or outside tenant scope."},
        )
        raise PermissionError(
            f"{entity_type} not found or outside tenant scope."
        )

    def audit(self, context, action, entity_type, entity_id, metadata=None):
        return self.audit_service.record(
            context,
            action=getattr(action, "value", action),
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )
