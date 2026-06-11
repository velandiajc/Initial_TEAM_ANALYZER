from enum import Enum

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import FormulaVersion
from app.models.risk import RiskRuleVersion


class GovernanceRole(Enum):
    KPI_OWNER = "kpi_owner"
    KPI_STEWARD = "kpi_steward"
    KPI_APPROVER = "kpi_approver"
    PERFORMANCE_COACH = "performance_coach"
    PERFORMANCE_MANAGER = "performance_manager"
    LEADERSHIP = "leadership"
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
    REGISTER_SOURCE_TYPE = "register_source_type"
    VALIDATE_OPERATIONAL_SOURCE = "validate_operational_source"
    VIEW_OPERATIONAL_SOURCE = "view_operational_source"
    EVALUATE_RISK = "evaluate_risk"
    VIEW_RISK_RESULTS = "view_risk_results"
    MANAGE_RISK_DEFINITIONS = "manage_risk_definitions"
    MANAGE_RISK_RULES = "manage_risk_rules"


class CoachingPermission(Enum):
    VIEW_COACHING_SESSION = "view_coaching_session"
    CREATE_COACHING_SESSION = "create_coaching_session"
    EDIT_COACHING_SESSION = "edit_coaching_session"
    CREATE_COMMITMENT = "create_commitment"
    UPDATE_COMMITMENT = "update_commitment"
    CREATE_FOLLOWUP = "create_followup"
    VIEW_PERFORMANCE_TIMELINE = "view_performance_timeline"
    VIEW_PRIVATE_COACHING_NOTE = "view_private_coaching_note"


class RBACService:
    ROLE_PERMISSIONS = {
        GovernanceRole.GOVERNANCE_ADMIN.value: {
            permission.value
            for permission in KPIPermission
        } | {
            permission.value
            for permission in CoachingPermission
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
            KPIPermission.EVALUATE_RISK.value,
            KPIPermission.VIEW_RISK_RESULTS.value,
            KPIPermission.MANAGE_RISK_DEFINITIONS.value,
            KPIPermission.MANAGE_RISK_RULES.value,
        },
        GovernanceRole.KPI_STEWARD.value: {
            KPIPermission.WRITE_THRESHOLD.value,
            KPIPermission.SUBMIT_FORMULA.value,
            KPIPermission.VIEW_GOVERNANCE.value,
            KPIPermission.VIEW_KPI_RESULTS.value,
            KPIPermission.MANAGE_RISK_RULES.value,
            KPIPermission.VIEW_RISK_RESULTS.value,
        },
        GovernanceRole.KPI_APPROVER.value: {
            KPIPermission.APPROVE_FORMULA.value,
            KPIPermission.CHANGE_LIFECYCLE.value,
            KPIPermission.VIEW_GOVERNANCE.value,
            KPIPermission.VIEW_KPI_RESULTS.value,
            KPIPermission.MANAGE_RISK_RULES.value,
            KPIPermission.MANAGE_RISK_DEFINITIONS.value,
            KPIPermission.VIEW_RISK_RESULTS.value,
        },
        GovernanceRole.PERFORMANCE_COACH.value: {
            CoachingPermission.VIEW_COACHING_SESSION.value,
            CoachingPermission.CREATE_COACHING_SESSION.value,
            CoachingPermission.EDIT_COACHING_SESSION.value,
            CoachingPermission.CREATE_COMMITMENT.value,
            CoachingPermission.UPDATE_COMMITMENT.value,
            CoachingPermission.CREATE_FOLLOWUP.value,
            CoachingPermission.VIEW_PERFORMANCE_TIMELINE.value,
        },
        GovernanceRole.PERFORMANCE_MANAGER.value: {
            permission.value
            for permission in CoachingPermission
        },
        GovernanceRole.LEADERSHIP.value: {
            CoachingPermission.VIEW_COACHING_SESSION.value,
            CoachingPermission.VIEW_PERFORMANCE_TIMELINE.value,
            CoachingPermission.VIEW_PRIVATE_COACHING_NOTE.value,
        },
    }

    def can(
        self,
        context: TenantContext | None,
        permission: KPIPermission | CoachingPermission | str
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
        permission: KPIPermission | CoachingPermission | str
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

    def can_approve_risk_rule(
        self,
        context: TenantContext | None,
        rule_version: RiskRuleVersion
    ) -> bool:
        context = require_tenant_context(context)

        if context.user_id == rule_version.created_by:
            return False

        return self.can(context, KPIPermission.MANAGE_RISK_RULES)

    def require_risk_rule_approval(
        self,
        context: TenantContext | None,
        rule_version: RiskRuleVersion
    ) -> None:
        context = require_tenant_context(context)

        if context.user_id == rule_version.created_by:
            raise PermissionError("Creator cannot approve own risk rule.")

        self.require_permission(context, KPIPermission.MANAGE_RISK_RULES)

    def _permission_value(
        self,
        permission: KPIPermission | CoachingPermission | str
    ) -> str:
        if isinstance(permission, (KPIPermission, CoachingPermission)):
            return permission.value

        return str(permission).strip().lower()
