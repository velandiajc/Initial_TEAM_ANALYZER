from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.risk import (
    RiskDefinitionLifecycle,
    RiskLevel,
    RiskRuleStatus,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.risk_registry_service import RiskRegistryService
from app.services.risk_rule_version_service import RiskRuleConflictError
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_risk_repository import SQLiteRiskDefinitionRepository


def context(role=GovernanceRole.KPI_OWNER, tenant_id="tenant-1", user_id="owner-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles={role.value},
    )


def create_services(tmp_path):
    database = DatabaseService(tmp_path / "risk.db")
    database.initialize()
    risk_repository = SQLiteRiskDefinitionRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)

    return {
        "audit_repository": audit_repository,
        "registry": RiskRegistryService(
            risk_repository,
            audit_service
        ),
        "risk_repository": risk_repository,
    }


def register_definition(registry):
    return registry.register_risk_definition(
        context(),
        risk_definition_id="csat-critical-risk",
        name="CSAT Critical Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )


def test_risk_definition_registration_is_tenant_scoped_and_audited(tmp_path):
    services = create_services(tmp_path)
    definition = register_definition(services["registry"])

    persisted = services["registry"].get_definition(
        context(),
        definition.risk_definition_id
    )
    hidden = services["registry"].get_definition(
        context(tenant_id="tenant-2"),
        definition.risk_definition_id
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert persisted is not None
    assert persisted.tenant_id == "tenant-1"
    assert hidden is None
    assert "risk_definition_registered" in actions


def test_risk_rule_requires_separate_approval_and_activation(tmp_path):
    services = create_services(tmp_path)
    register_definition(services["registry"])
    rule = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-critical-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "avg_csat",
            "operator": "lt",
            "threshold": 80,
            "risk_level": "critical",
        },
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )

    with pytest.raises(PermissionError, match="Creator cannot approve own risk rule"):
        services["registry"].approve_rule_version(
            context(),
            rule.rule_version_id
        )

    approved = services["registry"].approve_rule_version(
        context(GovernanceRole.KPI_APPROVER, user_id="approver-1"),
        rule.rule_version_id
    )
    active = services["registry"].activate_rule_version(
        context(GovernanceRole.KPI_APPROVER, user_id="approver-1"),
        rule.rule_version_id
    )

    assert approved.status == RiskRuleStatus.APPROVED
    assert active.status == RiskRuleStatus.ACTIVE
    assert active.is_approved_active()


def test_rule_versions_start_in_review_status(tmp_path):
    services = create_services(tmp_path)
    register_definition(services["registry"])

    rule = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-critical-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "csat",
            "operator": "lt",
            "threshold": 80,
        },
    )

    assert rule.status == RiskRuleStatus.REVIEW


def test_only_approved_rules_can_be_activated(tmp_path):
    services = create_services(tmp_path)
    register_definition(services["registry"])
    rule = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-critical-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "avg_csat",
            "operator": "lt",
            "threshold": 80,
        },
    )

    with pytest.raises(ValueError, match="approved"):
        services["registry"].activate_rule_version(
            context(GovernanceRole.KPI_APPROVER, user_id="approver-1"),
            rule.rule_version_id
        )


def test_active_rule_period_overlap_is_rejected(tmp_path):
    services = create_services(tmp_path)
    register_definition(services["registry"])
    first = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-critical-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "avg_csat",
            "operator": "lt",
            "threshold": 80,
        },
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 6, 30),
    )
    overlapping = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-critical-risk",
        version="2.0",
        handler_key="threshold",
        parameters={
            "metric_name": "avg_csat",
            "operator": "lt",
            "threshold": 85,
        },
        effective_from=datetime(2026, 6, 1),
        effective_to=datetime(2026, 12, 31),
    )
    approver = context(GovernanceRole.KPI_APPROVER, user_id="approver-1")
    services["registry"].approve_rule_version(approver, first.rule_version_id)
    services["registry"].activate_rule_version(approver, first.rule_version_id)
    services["registry"].approve_rule_version(approver, overlapping.rule_version_id)

    with pytest.raises(RiskRuleConflictError, match="overlaps"):
        services["registry"].activate_rule_version(
            approver,
            overlapping.rule_version_id
        )


def test_risk_definition_lifecycle_change_requires_approver_role(tmp_path):
    services = create_services(tmp_path)
    register_definition(services["registry"])

    definition = services["registry"].change_lifecycle(
        context(GovernanceRole.KPI_APPROVER, user_id="approver-1"),
        "csat-critical-risk",
        RiskDefinitionLifecycle.ACTIVE,
    )

    assert definition.lifecycle == RiskDefinitionLifecycle.ACTIVE


def test_approved_lifecycle_and_status_values_are_primary():
    assert [item.value for item in RiskDefinitionLifecycle] == [
        "draft",
        "review",
        "approved",
        "active",
        "deprecated",
        "retired",
    ]
    assert [item.value for item in RiskRuleStatus] == [
        "draft",
        "review",
        "approved",
        "active",
        "deprecated",
        "retired",
    ]
    assert "pending_approval" not in [
        item.value
        for item in RiskDefinitionLifecycle
    ]
    assert "archived" not in [
        item.value
        for item in RiskDefinitionLifecycle
    ]


def test_legacy_values_are_normalized_without_being_primary():
    assert RiskLevel.from_value("moderate") == RiskLevel.MEDIUM
    assert (
        RiskDefinitionLifecycle.from_value("pending_approval")
        == RiskDefinitionLifecycle.REVIEW
    )
    assert (
        RiskDefinitionLifecycle.from_value("archived")
        == RiskDefinitionLifecycle.DEPRECATED
    )
    assert RiskRuleStatus.from_value("pending_approval") == RiskRuleStatus.REVIEW
