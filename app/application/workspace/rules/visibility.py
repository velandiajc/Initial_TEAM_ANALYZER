from app.core.permissions import RBACService, WorkspacePermission
from app.core.tenant_context import require_tenant_context
from app.domain.performance.value_objects import CoachingNoteVisibility


class WorkspaceVisibilityRules:
    def __init__(self, rbac_service=None):
        self.rbac_service = rbac_service or RBACService()

    def validate_request(self, context, request):
        context = require_tenant_context(context)
        if context.tenant_id != request.tenant_id:
            raise PermissionError("Workspace request tenant mismatch.")
        if context.user_id != request.requester_id:
            raise PermissionError("Workspace requester identity mismatch.")
        return context

    def require(self, context, permission):
        self.rbac_service.require_permission(context, permission)

    def can_view_note(self, context, visibility):
        visibility = CoachingNoteVisibility.from_value(visibility)
        if visibility == CoachingNoteVisibility.SHARED:
            return True
        if visibility == CoachingNoteVisibility.MANAGER_ONLY:
            return self.rbac_service.can(
                context,
                WorkspacePermission.VIEW_PRIVATE_COACHING_NOTES,
            )
        if visibility == CoachingNoteVisibility.LEADERSHIP_ONLY:
            return self.rbac_service.can(
                context,
                WorkspacePermission.VIEW_LEADERSHIP_NOTES,
            )
        return False
