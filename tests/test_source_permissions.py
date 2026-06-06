import pytest

from app.core.permissions import GovernanceRole, KPIPermission, RBACService
from app.core.tenant_context import TenantContext


def context(role=None):
    roles = {role.value} if role else set()

    return TenantContext(
        tenant_id="tenant-1",
        user_id="user-1",
        roles=roles,
    )


def test_governance_admin_can_manage_operational_sources():
    rbac = RBACService()
    admin = context(GovernanceRole.GOVERNANCE_ADMIN)

    assert rbac.can(admin, KPIPermission.REGISTER_SOURCE_TYPE)
    assert rbac.can(admin, KPIPermission.VALIDATE_OPERATIONAL_SOURCE)
    assert rbac.can(admin, KPIPermission.VIEW_OPERATIONAL_SOURCE)


def test_source_permissions_do_not_change_existing_kpi_permissions():
    rbac = RBACService()
    owner = context(GovernanceRole.KPI_OWNER)
    approver = context(GovernanceRole.KPI_APPROVER)

    assert rbac.can(owner, KPIPermission.CALCULATE_KPI)
    assert rbac.can(owner, KPIPermission.VIEW_KPI_RESULTS)
    assert not rbac.can(approver, KPIPermission.CALCULATE_KPI)
    assert rbac.can(approver, KPIPermission.VIEW_KPI_RESULTS)


def test_non_admin_source_permissions_are_rejected():
    rbac = RBACService()
    owner = context(GovernanceRole.KPI_OWNER)
    no_role = context()

    with pytest.raises(PermissionError, match="register_source_type"):
        rbac.require_permission(owner, KPIPermission.REGISTER_SOURCE_TYPE)

    with pytest.raises(PermissionError, match="validate_operational_source"):
        rbac.require_permission(
            no_role,
            KPIPermission.VALIDATE_OPERATIONAL_SOURCE
        )

    with pytest.raises(PermissionError, match="view_operational_source"):
        rbac.require_permission(no_role, KPIPermission.VIEW_OPERATIONAL_SOURCE)
