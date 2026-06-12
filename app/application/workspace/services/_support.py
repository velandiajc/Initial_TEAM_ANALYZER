from app.application.workspace.rules import (
    WorkspaceAuditEvent,
    WorkspaceLineageRules,
    WorkspaceSuppressionRules,
    WorkspaceVisibilityRules,
)


class WorkspaceServiceSupport:
    def __init__(self, audit_service, rbac_service=None):
        self.audit_service = audit_service
        self.visibility = WorkspaceVisibilityRules(rbac_service)
        self.suppression = WorkspaceSuppressionRules()
        self.lineage = WorkspaceLineageRules()

    def authorize(
        self,
        context,
        request,
        permission,
        entity_type,
        entity_id,
    ):
        try:
            context = self.visibility.validate_request(context, request)
        except PermissionError as exc:
            event = (
                WorkspaceAuditEvent.CROSS_TENANT_WORKSPACE_ACCESS_DENIED
                if context.tenant_id != request.tenant_id
                else WorkspaceAuditEvent.SUPERVISOR_WORKSPACE_ACCESS_DENIED
            )
            self.audit(
                context,
                event,
                entity_type,
                entity_id,
                {
                    "requested_tenant_id": request.tenant_id,
                    "permission": permission.value,
                    "suppression_reason_code": "REQUEST_SCOPE_DENIED",
                },
            )
            raise
        try:
            self.visibility.require(context, permission)
        except PermissionError:
            self.audit(
                context,
                WorkspaceAuditEvent.SUPERVISOR_WORKSPACE_ACCESS_DENIED,
                entity_type,
                entity_id,
                {
                    "permission": permission.value,
                    "suppression_reason_code": "PERMISSION_DENIED",
                },
            )
            raise
        return context

    def require_tenant(self, context, records, entity_type, entity_id):
        for record in records:
            tenant_id = getattr(record, "tenant_id", None)
            if tenant_id != context.tenant_id:
                self.audit(
                    context,
                    WorkspaceAuditEvent.CROSS_TENANT_WORKSPACE_ACCESS_DENIED,
                    entity_type,
                    entity_id,
                    {
                        "permission": "tenant_scope",
                        "suppression_reason_code": "CROSS_TENANT_RECORD",
                    },
                )
                raise PermissionError("Workspace record tenant mismatch.")

    def audit_suppression(
        self,
        context,
        entity_type,
        entity_id,
        reasons,
    ):
        for reason in sorted(set(reasons)):
            self.audit(
                context,
                WorkspaceAuditEvent.RESTRICTED_WORKSPACE_DATA_SUPPRESSED,
                entity_type,
                entity_id,
                {"suppression_reason_code": reason},
            )

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
            action=getattr(action, "value", action),
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )
