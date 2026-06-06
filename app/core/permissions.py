from enum import Enum

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import FormulaVersion


class GovernanceRole(Enum):
    KPI_OWNER = "kpi_owner"
    KPI_STEWARD = "kpi_steward"
    KPI_APPROVER = "kpi_approver"
    GOVERNANCE_ADMIN = "governance_admin"


class KPIPermission(Enum):
    REGISTER_KPI = "register_kpi"
    UPDATE_OWNERSHIP = "update_ownership"
    WRITE_THRESHOLD = "write_threshold"
    SUBMIT_FORMULA = "submit_formula"
    APPROVE_FORMULA = "approve_formula"
    CHANGE_LIFECYCLE = "change_lifecycle"
    VIEW_GOVERNANCE = "view_governance"
    CALCULATE_KPI = "calculate_kpi"
    VIEW_KPI_RESULTS = "view_kpi_results"


class RBACService:
    ROLE_PERMISSIONS = {
        GovernanceRole.GOVERNANCE_ADMIN.value: {
            permission.value
            for permission in KPIPermission
        },
        GovernanceRole.KPI_OWNER.value: {
            KPIPermission.REGISTER_KPI.value,
            KPIPermission.UPDATE_OWNERSHIP.value,
            KPIPermission.WRITE_THRESHOLD.value,
            KPIPermission.SUBMIT_FORMULA.value,
            KPIPermission.CHANGE_LIFECYCLE.value,
            KPIPermission.VIEW_GOVERNANCE.value,
            KPIPermission.CALCULATE_KPI.value,
            KPIPermission.VIEW_KPI_RESULTS.value,
        },
        GovernanceRole.KPI_STEWARD.value: {
            KPIPermission.WRITE_THRESHOLD.value,
            KPIPermission.SUBMIT_FORMULA.value,
            KPIPermission.VIEW_GOVERNANCE.value,
            KPIPermission.VIEW_KPI_RESULTS.value,
        },
        GovernanceRole.KPI_APPROVER.value: {
            KPIPermission.APPROVE_FORMULA.value,
            KPIPermission.CHANGE_LIFECYCLE.value,
            KPIPermission.VIEW_GOVERNANCE.value,
            KPIPermission.VIEW_KPI_RESULTS.value,
        },
    }

    def can(
        self,
        context: TenantContext | None,
        permission: KPIPermission | str
    ) -> bool:
        context = require_tenant_context(context)
        permission_value = self._permission_value(permission)

        return any(
            permission_value in self.ROLE_PERMISSIONS.get(role, set())
            for role in context.roles
        )

    def require_permission(
        self,
        context: TenantContext | None,
        permission: KPIPermission | str
    ) -> None:
        if not self.can(context, permission):
            raise PermissionError(
                f"User is not allowed to {self._permission_value(permission)}."
            )

    def can_approve_formula(
        self,
        context: TenantContext | None,
        formula_version: FormulaVersion
    ) -> bool:
        context = require_tenant_context(context)

        if context.user_id == formula_version.created_by:
            return False

        return self.can(context, KPIPermission.APPROVE_FORMULA)

    def require_formula_approval(
        self,
        context: TenantContext | None,
        formula_version: FormulaVersion
    ) -> None:
        context = require_tenant_context(context)

        if context.user_id == formula_version.created_by:
            raise PermissionError("Creator cannot approve own formula.")

        self.require_permission(context, KPIPermission.APPROVE_FORMULA)

    def _permission_value(self, permission: KPIPermission | str) -> str:
        if isinstance(permission, KPIPermission):
            return permission.value

        return str(permission).strip().lower()
