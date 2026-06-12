import pytest

from app.core.tenant_context import TenantContext
from app.services.kpi_audit_service import sanitize_audit_metadata
from tests.integration.operational_impact.support import (
    build_stack,
    context,
    create_active_framework,
    create_kpi_results,
    create_risk_result,
    impact_request,
    prepare_stack,
    register_governed_inputs,
)


def unauthorized_context():
    return TenantContext(
        tenant_id="tenant-1",
        user_id="unauthorized-1",
        roles=set(),
    )


def test_unauthorized_calculation_and_view_are_denied_and_audited(tmp_path):
    stack, baseline, _ = prepare_stack(tmp_path)
    unauthorized = unauthorized_context()

    with pytest.raises(PermissionError, match="calculate_operational_impact"):
        stack["services"]["assessments"].calculate_impact(
            unauthorized,
            impact_request(baseline),
        )
    with pytest.raises(PermissionError, match="view_operational_impact"):
        stack["services"]["assessments"].get_assessment(
            unauthorized,
            "missing",
        )
    actions = {
        event.action
        for event in stack["audit_repository"].list_events(unauthorized)
    }
    assert "OPERATIONAL_IMPACT_ACCESS_DENIED" in actions


def test_unauthorized_definition_creation_and_approval_are_rejected(tmp_path):
    stack = build_stack(tmp_path)
    unauthorized = unauthorized_context()

    with pytest.raises(PermissionError, match="create_operational_impact"):
        stack["services"]["definitions"].create_definition(
            unauthorized,
            "impact",
            "Impact",
            "Governed impact.",
            "performance",
            "owner-1",
            "steward-1",
            "1.0",
            __import__("datetime").date(2026, 6, 1),
        )
    with pytest.raises(PermissionError, match="approve_operational_impact"):
        stack["services"]["definitions"].approve_definition(
            unauthorized,
            "impact",
            "1.0",
        )


def test_creator_cannot_approve_own_definition(tmp_path):
    stack = build_stack(tmp_path)
    owner = context()
    definition = stack["services"]["definitions"].create_definition(
        owner,
        "impact",
        "Impact",
        "Governed impact.",
        "performance",
        "owner-1",
        "steward-1",
        "1.0",
        __import__("datetime").date(2026, 6, 1),
    )

    with pytest.raises(PermissionError, match="approve"):
        stack["services"]["definitions"].approve_definition(
            owner,
            definition.impact_definition_id,
            definition.impact_definition_version,
        )


def test_cross_tenant_impact_inputs_are_rejected_and_audited(tmp_path):
    stack, _, _ = prepare_stack(tmp_path)
    register_governed_inputs(stack, tenant_id="tenant-2")
    tenant_two_results = create_kpi_results(
        stack,
        "tenant-two",
        50,
        tenant_id="tenant-2",
    )
    manager = context(role="performance_manager", user_id="manager-1")

    with pytest.raises(PermissionError, match="tenant scope"):
        stack["services"]["assessments"].calculate_impact(
            manager,
            impact_request(tenant_two_results),
        )
    actions = {
        event.action
        for event in stack["audit_repository"].list_events(manager)
    }
    assert "OPERATIONAL_IMPACT_ACCESS_DENIED" in actions


def test_cross_tenant_repository_write_is_rejected(tmp_path):
    stack, baseline, _ = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
    )

    with pytest.raises(PermissionError, match="tenant-scoped"):
        stack["repositories"]["assessments"].save(
            context(
                role="performance_manager",
                tenant_id="tenant-2",
                user_id="manager-2",
            ),
            impact,
        )


def test_cross_tenant_definition_and_impact_views_are_rejected(tmp_path):
    stack, baseline, _ = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
    )
    foreign_manager = context(
        role="performance_manager",
        tenant_id="tenant-2",
        user_id="manager-2",
    )

    with pytest.raises(PermissionError, match="tenant scope"):
        stack["services"]["definitions"].get_active_definition(
            foreign_manager,
            "operational-impact",
        )
    with pytest.raises(PermissionError, match="tenant scope"):
        stack["services"]["assessments"].get_assessment(
            foreign_manager,
            impact.impact_assessment_id,
        )


def test_missing_lineage_or_versions_cannot_be_persisted(tmp_path):
    stack, baseline, risk = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
    )
    priority = stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        impact.impact_assessment_id,
    )

    for source, field_name, message in (
        (impact, "lineage_id", "lineage_id"),
        (impact, "impact_definition_version", "impact_definition_version"),
        (priority, "risk_rule_version", "risk_rule_version"),
    ):
        original = getattr(source, field_name)
        object.__setattr__(source, field_name, "")
        repository = (
            stack["repositories"]["assessments"]
            if hasattr(source, "impact_factor_ids")
            else stack["repositories"]["priorities"]
        )
        try:
            with pytest.raises(ValueError, match=message):
                repository.save(manager, source)
        finally:
            object.__setattr__(source, field_name, original)


def test_priority_rejects_inaccessible_cross_tenant_inputs(tmp_path):
    stack, baseline, _ = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
    )
    register_governed_inputs(stack, tenant_id="tenant-2")
    foreign_risk = create_risk_result(
        stack,
        result_id="tenant-two-risk",
        tenant_id="tenant-2",
    )

    with pytest.raises(PermissionError, match="tenant scope"):
        stack["services"]["priorities"].calculate_priority(
            manager,
            foreign_risk.result_id,
            impact.impact_assessment_id,
        )
    actions = {
        event.action
        for event in stack["audit_repository"].list_events(manager)
    }
    assert "RISK_PRIORITY_ACCESS_DENIED" in actions


def test_unauthorized_priority_calculation_and_view_are_rejected(tmp_path):
    stack, baseline, risk = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
    )
    priority = stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        impact.impact_assessment_id,
    )
    unauthorized = unauthorized_context()

    with pytest.raises(PermissionError, match="calculate_risk_priority"):
        stack["services"]["priorities"].calculate_priority(
            unauthorized,
            risk.result_id,
            impact.impact_assessment_id,
        )
    with pytest.raises(PermissionError, match="view_risk_priority"):
        stack["services"]["priorities"].get_priority(
            unauthorized,
            priority.priority_assessment_id,
        )
    actions = {
        event.action
        for event in stack["audit_repository"].list_events(unauthorized)
    }
    assert "RISK_PRIORITY_ACCESS_DENIED" in actions


def test_cross_tenant_priority_view_is_rejected(tmp_path):
    stack, baseline, risk = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
    )
    priority = stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        impact.impact_assessment_id,
    )
    foreign_manager = context(
        role="performance_manager",
        tenant_id="tenant-2",
        user_id="manager-2",
    )

    with pytest.raises(PermissionError, match="tenant scope"):
        stack["services"]["priorities"].get_priority(
            foreign_manager,
            priority.priority_assessment_id,
        )


def test_audit_metadata_suppresses_raw_sensitive_content():
    sanitized = sanitize_audit_metadata({
        "lineage_id": "safe",
        "raw_transcript": "4111111111111111",
        "recording_url": "secure://recording",
        "customer_comment": "private",
        "coaching_note": "private",
        "cvv": "123",
    })

    assert sanitized == {"lineage_id": "safe"}


def test_framework_rejects_non_governed_factor_sources(tmp_path):
    stack = build_stack(tmp_path)
    register_governed_inputs(stack)
    create_active_framework(stack)
    owner = context()

    with pytest.raises(ValueError, match="MVP set"):
        stack["services"]["factors"].create_factor(
            owner,
            "raw-transcript-factor",
            "operational-impact",
            "1.0",
            "Raw Transcript",
            "Disallowed raw input.",
            "transcript:raw",
            0.1,
            "HIGHER_IS_WORSE",
            "1.0",
            0,
            100,
            "1.0",
            "owner-1",
            "steward-1",
            __import__("datetime").date(2026, 6, 1),
        )
