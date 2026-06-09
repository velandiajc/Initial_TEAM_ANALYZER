import pytest

from app.core.permissions import (
    GovernanceRole,
    KPIPermission,
    RBACService,
)
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import FormulaVersion


def test_tenant_context_is_required():
    with pytest.raises(ValueError, match="TenantContext required"):
        require_tenant_context(None)


def test_governance_roles_grant_expected_permissions():
    rbac = RBACService()
    owner_context = TenantContext(
        tenant_id="tenant-1",
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )
    approver_context = TenantContext(
        tenant_id="tenant-1",
        user_id="approver-1",
        roles={GovernanceRole.KPI_APPROVER.value},
    )

    assert rbac.can(owner_context, KPIPermission.REGISTER_KPI)
    assert rbac.can(owner_context, KPIPermission.SUBMIT_FORMULA)
    assert rbac.can(owner_context, KPIPermission.CALCULATE_KPI)
    assert rbac.can(owner_context, KPIPermission.VIEW_KPI_RESULTS)
    assert rbac.can(owner_context, KPIPermission.MANAGE_RISK_DEFINITIONS)
    assert rbac.can(owner_context, KPIPermission.MANAGE_RISK_RULES)
    assert rbac.can(owner_context, KPIPermission.EVALUATE_RISK)
    assert not rbac.can(owner_context, KPIPermission.APPROVE_FORMULA)
    assert rbac.can(approver_context, KPIPermission.APPROVE_FORMULA)
    assert rbac.can(approver_context, KPIPermission.VIEW_KPI_RESULTS)
    assert rbac.can(approver_context, KPIPermission.MANAGE_RISK_RULES)
    assert rbac.can(approver_context, KPIPermission.MANAGE_RISK_DEFINITIONS)
    assert rbac.can(approver_context, KPIPermission.VIEW_RISK_RESULTS)
    assert not rbac.can(approver_context, KPIPermission.CALCULATE_KPI)
    assert not rbac.can(approver_context, KPIPermission.EVALUATE_RISK)


def test_creator_cannot_approve_own_formula_even_with_approver_role():
    rbac = RBACService()
    context = TenantContext(
        tenant_id="tenant-1",
        user_id="owner-1",
        roles={GovernanceRole.KPI_APPROVER.value},
    )
    formula = FormulaVersion(
        formula_version_id="formula-1",
        tenant_id="tenant-1",
        kpi_id="csat",
        version="1.0",
        expression="survey_score_average",
        created_by="owner-1",
    )

    assert not rbac.can_approve_formula(context, formula)

    with pytest.raises(PermissionError, match="Creator cannot approve own formula"):
        rbac.require_formula_approval(context, formula)


def test_permission_error_for_missing_role():
    rbac = RBACService()
    context = TenantContext(
        tenant_id="tenant-1",
        user_id="user-1",
    )

    with pytest.raises(PermissionError, match="register_kpi"):
        rbac.require_permission(context, KPIPermission.REGISTER_KPI)
