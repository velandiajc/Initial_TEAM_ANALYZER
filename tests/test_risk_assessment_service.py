from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.risk import (
    RiskAssessmentRequest,
    RiskAssessmentStatus,
    RiskDefinitionLifecycle,
    RiskLevel,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.risk_assessment_service import RiskAssessmentRejectedError
from app.services.risk_assessment_service import RiskAssessmentService
from app.services.risk_registry_service import RiskRegistryService
from app.services.risk_rule_handler_registry import (
    RiskRuleHandlerRegistry,
    ThresholdRiskRuleHandler,
)
from app.services.risk_rule_version_service import (
    MissingApprovedActiveRiskRuleError,
    RiskRuleVersionService,
)
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_risk_repository import SQLiteRiskDefinitionRepository


class FailingRiskHandler:
    def evaluate(self, request, rule_version):
        raise RuntimeError("risk source unavailable")


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
    rule_version_service = RiskRuleVersionService(risk_repository)
    handler_registry = RiskRuleHandlerRegistry()
    handler_registry.register("threshold", ThresholdRiskRuleHandler())

    return {
        "assessment": RiskAssessmentService(
            risk_repository,
            rule_version_service,
            handler_registry,
            audit_service,
        ),
        "audit_repository": audit_repository,
        "handler_registry": handler_registry,
        "registry": RiskRegistryService(
            risk_repository,
            audit_service,
            rule_version_service=rule_version_service,
        ),
        "risk_repository": risk_repository,
    }


def assessment_request(metric_value=72, risk_definition_id="csat-critical-risk"):
    return RiskAssessmentRequest(
        risk_definition_id=risk_definition_id,
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        entity_type="agent",
        entity_id="agent-1",
        metric_values={
            "avg_csat": metric_value,
        },
        source_reference="survey:unit-test",
    )


def create_active_risk_rule(services):
    owner = context()
    approver = context(
        GovernanceRole.KPI_APPROVER,
        user_id="approver-1"
    )
    registry = services["registry"]
    registry.register_risk_definition(
        owner,
        risk_definition_id="csat-critical-risk",
        name="CSAT Critical Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    rule = registry.submit_rule_version(
        owner,
        risk_definition_id="csat-critical-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "avg_csat",
            "operator": "lt",
            "threshold": 80,
            "risk_level": "critical",
            "default_risk_level": "low",
            "reason": "Average CSAT below governed threshold.",
        },
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )
    registry.approve_rule_version(approver, rule.rule_version_id)
    registry.activate_rule_version(approver, rule.rule_version_id)
    registry.change_lifecycle(
        approver,
        "csat-critical-risk",
        RiskDefinitionLifecycle.ACTIVE,
    )

    return rule


def test_risk_assessment_persists_traceable_result(tmp_path):
    services = create_services(tmp_path)
    rule = create_active_risk_rule(services)

    result = services["assessment"].assess_risk(
        context(),
        assessment_request()
    )
    persisted = services["risk_repository"].get_result(
        context(),
        result.result_id
    )

    assert result.status == RiskAssessmentStatus.SUCCESS
    assert result.risk_level == RiskLevel.CRITICAL
    assert result.rule_version_id == rule.rule_version_id
    assert result.rule_version_number == "1.0"
    assert result.evidence["metric_name"] == "avg_csat"
    assert persisted is not None
    assert persisted.assessment_run_id == result.assessment_run_id


def test_risk_assessment_generates_success_audit_events(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)

    services["assessment"].assess_risk(
        context(),
        assessment_request()
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert "RISK_ASSESSMENT_REQUESTED" in actions
    assert "RISK_ASSESSMENT_STARTED" in actions
    assert "RISK_RULE_SELECTED" in actions
    assert "RISK_ASSESSMENT_COMPLETED" in actions


def test_only_approved_active_rule_executes(tmp_path):
    services = create_services(tmp_path)
    registry = services["registry"]
    registry.register_risk_definition(
        context(),
        risk_definition_id="csat-critical-risk",
        name="CSAT Critical Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    registry.submit_rule_version(
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
        effective_to=datetime(2026, 12, 31),
    )
    registry.change_lifecycle(
        context(GovernanceRole.KPI_APPROVER, user_id="approver-1"),
        "csat-critical-risk",
        RiskDefinitionLifecycle.ACTIVE,
    )

    with pytest.raises(MissingApprovedActiveRiskRuleError):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )

    assert services["risk_repository"].list_results_for_definition(
        context(),
        "csat-critical-risk"
    ) == []


def test_inactive_risk_definition_rejects_assessment(tmp_path):
    services = create_services(tmp_path)
    registry = services["registry"]
    registry.register_risk_definition(
        context(),
        risk_definition_id="csat-critical-risk",
        name="CSAT Critical Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )

    with pytest.raises(RiskAssessmentRejectedError, match="active"):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )


def test_default_low_risk_is_persisted_when_threshold_not_triggered(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)

    result = services["assessment"].assess_risk(
        context(),
        assessment_request(metric_value=92)
    )

    assert result.risk_level == RiskLevel.LOW
    assert result.evidence["triggered"] is False
    assert result.reason == "No governed risk threshold matched."


def test_missing_metric_rejects_assessment_and_does_not_persist_result(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)
    request = assessment_request()
    request.metric_values = {}

    with pytest.raises(ValueError, match="Missing risk metric"):
        services["assessment"].assess_risk(
            context(),
            request
        )

    assert services["risk_repository"].list_results_for_definition(
        context(),
        "csat-critical-risk"
    ) == []


def test_viewing_result_requires_permission_and_is_audited(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)
    result = services["assessment"].assess_risk(
        context(),
        assessment_request()
    )

    viewed = services["assessment"].get_result(
        context(),
        result.result_id
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert viewed is not None
    assert "RISK_RESULT_VIEWED" in actions


def test_unauthorized_user_cannot_assess_risk(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)

    with pytest.raises(PermissionError, match="assess_risk"):
        services["assessment"].assess_risk(
            TenantContext(
                tenant_id="tenant-1",
                user_id="analyst-1",
                roles=set(),
            ),
            assessment_request()
        )


def test_handler_failure_generates_failed_audit_event(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)
    services["handler_registry"].register("failing_handler", FailingRiskHandler())
    rule = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-critical-risk",
        version="2.0",
        handler_key="failing_handler",
        parameters={
            "metric_name": "avg_csat",
        },
        effective_from=datetime(2027, 1, 1),
        effective_to=datetime(2027, 12, 31),
    )
    approver = context(GovernanceRole.KPI_APPROVER, user_id="approver-1")
    services["registry"].approve_rule_version(approver, rule.rule_version_id)
    services["registry"].activate_rule_version(approver, rule.rule_version_id)
    request = assessment_request()
    request.period_start = datetime(2027, 3, 1)
    request.period_end = datetime(2027, 3, 31)

    with pytest.raises(RuntimeError, match="risk source unavailable"):
        services["assessment"].assess_risk(
            context(),
            request
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]
    assert "RISK_ASSESSMENT_FAILED" in actions
