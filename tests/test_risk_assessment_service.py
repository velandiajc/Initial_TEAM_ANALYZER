from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import (
    FormulaStatus,
    FormulaVersion,
    KPIDefinition,
    KPIDomain,
)
from app.models.kpi_calculation import (
    KPICalculationResult,
    KPICalculationStatus,
)
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
from app.services.sqlite_kpi_calculation_result_repository import (
    SQLiteKPICalculationResultRepository,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)
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
    definition_repository = SQLiteKPIDefinitionRepository(database)
    risk_repository = SQLiteRiskDefinitionRepository(database)
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)
    rule_version_service = RiskRuleVersionService(risk_repository)
    handler_registry = RiskRuleHandlerRegistry()
    handler_registry.register("threshold", ThresholdRiskRuleHandler())
    kpi_result_repository = SQLiteKPICalculationResultRepository(
        database,
        definition_repository
    )
    _register_kpi_definition(definition_repository)

    return {
        "assessment": RiskAssessmentService(
            risk_repository,
            rule_version_service,
            handler_registry,
            audit_service,
            kpi_result_repository,
        ),
        "audit_repository": audit_repository,
        "definition_repository": definition_repository,
        "handler_registry": handler_registry,
        "kpi_result_repository": kpi_result_repository,
        "registry": RiskRegistryService(
            risk_repository,
            audit_service,
            rule_version_service=rule_version_service,
        ),
        "risk_repository": risk_repository,
    }


def _register_kpi_definition(definition_repository, tenant_id="tenant-1"):
    definition_repository.upsert_definition(
        context(tenant_id=tenant_id),
        KPIDefinition(
            kpi_id="csat",
            tenant_id=tenant_id,
            name="CSAT",
            domain=KPIDomain.CUSTOMER_EXPERIENCE,
            owner_user_id="owner-1",
            steward_user_id="steward-1",
            created_by="owner-1",
        )
    )
    definition_repository.upsert_formula_version(
        context(tenant_id=tenant_id),
        FormulaVersion(
            formula_version_id=f"{tenant_id}-formula-1",
            tenant_id=tenant_id,
            kpi_id="csat",
            version="1.0",
            expression="count_records",
            created_by="owner-1",
            status=FormulaStatus.APPROVED,
            approved_by="approver-1",
            approved_at=datetime(2026, 1, 1),
        )
    )


def kpi_result(
    value=72,
    result_id="kpi-result-1",
    tenant_id="tenant-1",
    status=KPICalculationStatus.SUCCESS,
    data_quality_status="valid",
    period_start=datetime(2026, 3, 1),
    period_end=datetime(2026, 3, 31),
):
    return KPICalculationResult(
        tenant_id=tenant_id,
        result_id=result_id,
        kpi_id="csat",
        formula_version_id=f"{tenant_id}-formula-1",
        formula_version_number="1.0",
        period_start=period_start,
        period_end=period_end,
        scope={
            "agent_id": "agent-1"
        },
        value=value,
        status=status,
        data_quality_status=data_quality_status,
        source_reference="survey:2026-03",
        calculation_run_id="kpi-run-1",
        metadata={
            "source_record_ids": ["source-1"],
            "source_references": ["survey:2026-03"],
            "source_types": ["survey"],
            "source_version": ["v1"],
            "source_validation_status": ["valid"],
            "source_quality_summary": {"valid": 1},
            "lineage_id": ["lineage-1"],
        },
    )


def save_kpi_result(services, result=None):
    item = result or kpi_result()
    services["kpi_result_repository"].save(
        context(tenant_id=item.tenant_id),
        item
    )
    return item


def assessment_request(kpi_result_ids=None, risk_definition_id="csat-risk"):
    ids = ["kpi-result-1"] if kpi_result_ids is None else kpi_result_ids

    return RiskAssessmentRequest(
        risk_definition_id=risk_definition_id,
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        entity_type="agent",
        entity_id="agent-1",
        kpi_result_ids=ids,
    )


def raw_metric_request():
    return RiskAssessmentRequest(
        risk_definition_id="csat-risk",
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        entity_type="agent",
        entity_id="agent-1",
        metric_values={
            "csat": 72,
        },
    )


def create_active_risk_rule(
    services,
    risk_level="critical",
    default_risk_level="low",
    threshold=80,
    version="1.0",
    effective_from=datetime(2026, 1, 1),
    effective_to=datetime(2026, 12, 31),
    handler_key="threshold",
):
    owner = context()
    approver = context(
        GovernanceRole.KPI_APPROVER,
        user_id="approver-1"
    )
    registry = services["registry"]
    if registry.get_definition(owner, "csat-risk") is None:
        registry.register_risk_definition(
            owner,
            risk_definition_id="csat-risk",
            name="CSAT Risk",
            category="customer_experience",
            owner_user_id="owner-1",
            steward_user_id="steward-1",
            metadata={
                "version": "1.0"
            },
        )
    rule = registry.submit_rule_version(
        owner,
        risk_definition_id="csat-risk",
        version=version,
        handler_key=handler_key,
        parameters={
            "metric_name": "csat",
            "operator": "lt",
            "threshold": threshold,
            "risk_level": risk_level,
            "default_risk_level": default_risk_level,
            "reason": "CSAT below governed threshold.",
        },
        effective_from=effective_from,
        effective_to=effective_to,
    )
    registry.approve_rule_version(approver, rule.rule_version_id)
    registry.activate_rule_version(approver, rule.rule_version_id)
    registry.change_lifecycle(
        approver,
        "csat-risk",
        RiskDefinitionLifecycle.ACTIVE,
    )

    return rule


def test_cannot_evaluate_risk_from_raw_metric_values_only(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)

    with pytest.raises(RiskAssessmentRejectedError, match="KPI Result reference"):
        services["assessment"].assess_risk(
            context(),
            raw_metric_request()
        )


def test_can_evaluate_risk_from_governed_kpi_result_reference(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
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
    assert result.risk_score == 100.0
    assert result.rule_version_id == rule.rule_version_id
    assert result.rule_version_number == "1.0"
    assert result.risk_definition_version == "1.0"
    assert result.kpi_result_ids == ["kpi-result-1"]
    assert result.formula_versions == [{
        "kpi_id": "csat",
        "formula_version_id": "tenant-1-formula-1",
        "formula_version_number": "1.0",
    }]
    assert result.source_record_ids == ["source-1"]
    assert result.source_validation_lineage["source_validation_status"] == ["valid"]
    assert result.lineage_id == "lineage-1"
    assert result.evidence["metric_name"] == "csat"
    assert persisted is not None
    assert persisted.kpi_result_ids == ["kpi-result-1"]
    assert persisted.lineage_id == "lineage-1"


def test_missing_kpi_result_reference_is_rejected(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)
    request = assessment_request(kpi_result_ids=[])

    with pytest.raises(RiskAssessmentRejectedError, match="KPI Result reference"):
        services["assessment"].assess_risk(
            context(),
            request
        )


def test_missing_kpi_result_is_rejected(tmp_path):
    services = create_services(tmp_path)
    create_active_risk_rule(services)

    with pytest.raises(RiskAssessmentRejectedError, match="not found"):
        services["assessment"].assess_risk(
            context(),
            assessment_request(kpi_result_ids=["missing-result"])
        )


def test_failed_kpi_result_is_rejected(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(
        services,
        kpi_result(status=KPICalculationStatus.CALCULATION_ERROR)
    )
    create_active_risk_rule(services)

    with pytest.raises(RiskAssessmentRejectedError, match="successful"):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )


def test_untrusted_kpi_result_is_rejected(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(
        services,
        kpi_result(data_quality_status="untrusted")
    )
    create_active_risk_rule(services)

    with pytest.raises(RiskAssessmentRejectedError, match="trusted"):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )


def test_kpi_result_outside_assessment_period_is_rejected(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(
        services,
        kpi_result(
            period_start=datetime(2026, 2, 1),
            period_end=datetime(2026, 2, 28)
        )
    )
    create_active_risk_rule(services)

    with pytest.raises(RiskAssessmentRejectedError, match="outside"):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )


def test_cross_tenant_kpi_result_object_is_rejected(tmp_path):
    services = create_services(tmp_path)
    _register_kpi_definition(services["definition_repository"], tenant_id="tenant-2")
    create_active_risk_rule(services)
    request = assessment_request(kpi_result_ids=[])
    request.kpi_results = [
        kpi_result(tenant_id="tenant-2", result_id="tenant-2-result")
    ]

    with pytest.raises(PermissionError, match="tenant"):
        services["assessment"].assess_risk(
            context(),
            request
        )


def test_only_approved_active_rule_executes(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    registry = services["registry"]
    registry.register_risk_definition(
        context(),
        risk_definition_id="csat-risk",
        name="CSAT Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )
    registry.submit_rule_version(
        context(),
        risk_definition_id="csat-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "csat",
            "operator": "lt",
            "threshold": 80,
        },
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
    )
    registry.change_lifecycle(
        context(GovernanceRole.KPI_APPROVER, user_id="approver-1"),
        "csat-risk",
        RiskDefinitionLifecycle.ACTIVE,
    )

    with pytest.raises(MissingApprovedActiveRiskRuleError):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )

    assert services["risk_repository"].list_results_for_definition(
        context(),
        "csat-risk"
    ) == []


def test_inactive_risk_definition_rejects_evaluation(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    services["registry"].register_risk_definition(
        context(),
        risk_definition_id="csat-risk",
        name="CSAT Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )

    with pytest.raises(RiskAssessmentRejectedError, match="active"):
        services["assessment"].assess_risk(
            context(),
            assessment_request()
        )


@pytest.mark.parametrize(
    ("risk_level", "kpi_value", "expected_score"),
    [
        ("medium", 72, 50.0),
        ("high", 72, 75.0),
        ("critical", 72, 100.0),
    ]
)
def test_triggered_risk_scores_are_persisted(
    tmp_path,
    risk_level,
    kpi_value,
    expected_score
):
    services = create_services(tmp_path)
    save_kpi_result(services, kpi_result(value=kpi_value))
    create_active_risk_rule(services, risk_level=risk_level)

    result = services["assessment"].assess_risk(
        context(),
        assessment_request()
    )

    assert result.risk_level == RiskLevel.from_value(risk_level)
    assert result.risk_score == expected_score


def test_low_risk_score_is_persisted_when_threshold_not_triggered(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services, kpi_result(value=92))
    create_active_risk_rule(services)

    result = services["assessment"].assess_risk(
        context(),
        assessment_request()
    )

    assert result.risk_level == RiskLevel.LOW
    assert result.risk_score == 25.0
    assert result.evidence["triggered"] is False
    assert result.reason == "No governed risk threshold matched."


def test_viewing_result_requires_permission_and_is_audited(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
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


def test_unauthorized_user_cannot_evaluate_risk_and_is_audited(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    create_active_risk_rule(services)
    unauthorized = TenantContext(
        tenant_id="tenant-1",
        user_id="analyst-1",
        roles=set(),
    )

    with pytest.raises(PermissionError, match="evaluate_risk"):
        services["assessment"].assess_risk(
            unauthorized,
            assessment_request()
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(unauthorized)
    ]
    assert "RISK_ACCESS_DENIED" in actions


def test_unauthorized_user_cannot_view_risk_results_and_is_audited(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    create_active_risk_rule(services)
    result = services["assessment"].assess_risk(
        context(),
        assessment_request()
    )
    unauthorized = TenantContext(
        tenant_id="tenant-1",
        user_id="analyst-1",
        roles=set(),
    )

    with pytest.raises(PermissionError, match="view_risk_results"):
        services["assessment"].get_result(
            unauthorized,
            result.result_id
        )

    actions = [
        event.action
        for event in services["audit_repository"].list_events(unauthorized)
    ]
    assert "RISK_ACCESS_DENIED" in actions


def test_risk_evaluation_generates_approved_audit_events(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    create_active_risk_rule(services)

    services["assessment"].assess_risk(
        context(),
        assessment_request()
    )
    actions = [
        event.action
        for event in services["audit_repository"].list_events(context())
    ]

    assert "RISK_EVALUATION_REQUESTED" in actions
    assert "RISK_EVALUATION_STARTED" in actions
    assert "RISK_RULE_SELECTED" in actions
    assert "RISK_EVALUATION_COMPLETED" in actions
    assert "RISK_ASSESSMENT_REQUESTED" not in actions


def test_handler_failure_generates_failed_audit_event(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    create_active_risk_rule(services)
    services["handler_registry"].register("failing_handler", FailingRiskHandler())
    rule = services["registry"].submit_rule_version(
        context(),
        risk_definition_id="csat-risk",
        version="2.0",
        handler_key="failing_handler",
        parameters={
            "metric_name": "csat",
        },
        effective_from=datetime(2027, 1, 1),
        effective_to=datetime(2027, 12, 31),
    )
    approver = context(GovernanceRole.KPI_APPROVER, user_id="approver-1")
    services["registry"].approve_rule_version(approver, rule.rule_version_id)
    services["registry"].activate_rule_version(approver, rule.rule_version_id)
    future_result = kpi_result(
        result_id="kpi-result-2027",
        period_start=datetime(2027, 3, 1),
        period_end=datetime(2027, 3, 31)
    )
    save_kpi_result(services, future_result)
    request = assessment_request(kpi_result_ids=["kpi-result-2027"])
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
    assert "RISK_EVALUATION_FAILED" in actions


def test_audit_metadata_does_not_store_raw_metric_or_source_payloads(tmp_path):
    services = create_services(tmp_path)
    save_kpi_result(services)
    create_active_risk_rule(services)
    request = assessment_request()
    request.metadata = {
        "raw_metric_payload": {"csat": 72},
        "raw_source_data": {"customer_name": "Sensitive"},
        "safe_note": "allowed",
    }

    services["assessment"].assess_risk(
        context(),
        request
    )
    metadata = [
        event.metadata
        for event in services["audit_repository"].list_events(context())
        if event.action.startswith("RISK_")
    ]

    assert metadata
    assert all("raw_metric_payload" not in event for event in metadata)
    assert all("raw_source_data" not in event for event in metadata)
    assert all("customer_name" not in str(event) for event in metadata)
