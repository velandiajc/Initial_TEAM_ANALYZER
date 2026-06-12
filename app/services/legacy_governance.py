from app.core.permissions import RBACService
from app.core.tenant_context import TenantContext, require_tenant_context


class LegacyGovernanceSupport:
    ACCESS_DENIED_ACTION = "LEGACY_DATA_ACCESS_DENIED"

    def __init__(self, audit_service, rbac_service=None):
        if audit_service is None:
            raise ValueError("audit_service is required.")
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def require_context(
        self,
        context: TenantContext | None,
    ) -> TenantContext:
        return require_tenant_context(context)

    def require_permission(
        self,
        context,
        permission,
        entity_type,
        entity_id,
    ) -> None:
        try:
            self.rbac_service.require_permission(context, permission)
        except PermissionError as exc:
            self.audit(
                context,
                self.ACCESS_DENIED_ACTION,
                entity_type,
                entity_id,
                {"reason": str(exc)},
            )
            raise

    def audit(
        self,
        context,
        action,
        entity_type,
        entity_id,
        metadata=None,
    ):
        return self.audit_service.record(
            context,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )
