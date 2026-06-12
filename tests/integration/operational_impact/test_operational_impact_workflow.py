import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from tests.integration.operational_impact.support import (
    context,
    create_kpi_results,
    impact_request,
    prepare_stack,
)


def test_governed_impact_and_priority_workflow(tmp_path):
    stack, baseline, risk = prepare_stack(tmp_path)
    manager = context(
        role="performance_manager",
        user_id="manager-1",
    )

    impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
        impact_assessment_id="impact-assessment-1",
    )
    priority = stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        impact.impact_assessment_id,
        priority_assessment_id="priority-assessment-1",
    )
    persisted_impact = stack["repositories"]["assessments"].get_by_id(
        manager,
        impact.impact_assessment_id,
    )
    persisted_priority = stack["repositories"]["priorities"].get_by_id(
        manager,
        priority.priority_assessment_id,
    )

    assert persisted_impact.impact_score == 10
    assert persisted_impact.impact_level.value == "LOW"
    assert persisted_impact.impact_definition_version == "1.0"
    assert set(persisted_impact.impact_factor_versions.values()) == {"1.0"}
    assert set(persisted_impact.threshold_versions.values()) == {"1.0"}
    assert persisted_priority.risk_score_snapshot == 100
    assert persisted_priority.impact_score_snapshot == 10
    assert persisted_priority.priority_score == 10
    assert persisted_priority.priority_level.value == "MONITOR"
    assert persisted_priority.risk_definition_version == "1.0"
    assert persisted_priority.risk_rule_version == "1.0"
    with pytest.raises(FrozenInstanceError):
        persisted_impact.impact_score = 99
    with pytest.raises(FrozenInstanceError):
        persisted_priority.priority_score = 99
    with pytest.raises(TypeError):
        persisted_impact.weight_snapshots["factor-survey-volume"] = 0.99


def test_definition_and_factor_lifecycle_is_approved_and_active(tmp_path):
    stack, _, _ = prepare_stack(tmp_path)
    definition = stack["repositories"]["definitions"].get_active(
        context(),
        "operational-impact",
    )
    factors = stack["repositories"]["factors"].list_active_for_definition(
        context(),
        "operational-impact",
        "1.0",
    )

    assert definition.status.value == "ACTIVE"
    assert definition.approved_by == "approver-1"
    assert len(factors) == 5
    assert all(factor.status.value == "ACTIVE" for factor in factors)
    assert all(factor.approved_by == "approver-1" for factor in factors)


def test_calculation_and_view_actions_are_audited(tmp_path):
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
    stack["services"]["assessments"].get_assessment(
        manager,
        impact.impact_assessment_id,
    )
    stack["services"]["priorities"].get_priority(
        manager,
        priority.priority_assessment_id,
    )
    actions = {
        event.action
        for event in stack["audit_repository"].list_events(manager)
    }

    assert "OPERATIONAL_IMPACT_CALCULATED" in actions
    assert "OPERATIONAL_IMPACT_VIEWED" in actions
    assert "OPERATIONAL_IMPACT_DEFINITION_CREATED" in actions
    assert "OPERATIONAL_IMPACT_DEFINITION_APPROVED" in actions
    assert "OPERATIONAL_IMPACT_FACTOR_CREATED" in actions
    assert "OPERATIONAL_IMPACT_FACTOR_APPROVED" in actions
    assert "RISK_PRIORITY_CALCULATED" in actions
    assert "RISK_PRIORITY_VIEWED" in actions


def test_material_change_creates_timeline_event_and_noise_does_not(tmp_path):
    stack, baseline, risk = prepare_stack(tmp_path)
    manager = context(role="performance_manager", user_id="manager-1")
    first_impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(baseline),
        impact_assessment_id="impact-low",
    )
    stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        first_impact.impact_assessment_id,
        priority_assessment_id="priority-low",
    )
    assert stack["services"]["timeline"].get_timeline(
        manager,
        "employee-1",
    ) == []

    moderate_inputs = create_kpi_results(stack, "moderate", 30)
    moderate_impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(moderate_inputs),
        impact_assessment_id="impact-moderate",
    )
    stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        moderate_impact.impact_assessment_id,
        priority_assessment_id="priority-moderate",
    )
    assert stack["services"]["timeline"].get_timeline(
        manager,
        "employee-1",
    ) == []

    high_inputs = create_kpi_results(stack, "high", 60)
    high_impact = stack["services"]["assessments"].calculate_impact(
        manager,
        impact_request(high_inputs),
        impact_assessment_id="impact-high",
    )
    stack["services"]["priorities"].calculate_priority(
        manager,
        risk.result_id,
        high_impact.impact_assessment_id,
        priority_assessment_id="priority-high",
    )
    timeline = stack["services"]["timeline"].get_timeline(
        manager,
        "employee-1",
    )

    assert len(timeline) == 1
    assert timeline[0].impact_level_snapshot.value == "HIGH"
    assert timeline[0].priority_level_snapshot.value == "ESCALATE"
    actions = {
        event.action
        for event in stack["audit_repository"].list_events(manager)
    }
    assert "OPERATIONAL_IMPACT_TIMELINE_EVENT_CREATED" in actions


def test_impact_and_priority_history_is_database_immutable(tmp_path):
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

    with stack["database"].connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                """
                UPDATE operational_impact_assessments
                SET impact_score = 99
                WHERE tenant_id = ? AND impact_assessment_id = ?
                """,
                (manager.tenant_id, impact.impact_assessment_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            conn.execute(
                """
                DELETE FROM risk_priority_assessments
                WHERE tenant_id = ? AND priority_assessment_id = ?
                """,
                (manager.tenant_id, priority.priority_assessment_id),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                """
                UPDATE risk_priority_assessments
                SET priority_score = 99
                WHERE tenant_id = ? AND priority_assessment_id = ?
                """,
                (manager.tenant_id, priority.priority_assessment_id),
            )


def test_definition_and_factor_version_rows_cannot_be_deleted(tmp_path):
    stack, _, _ = prepare_stack(tmp_path)
    with stack["database"].connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            conn.execute(
                """
                DELETE FROM operational_impact_definitions
                WHERE tenant_id = 'tenant-1'
                """,
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                """
                UPDATE operational_impact_definitions
                SET name = 'Rewritten history'
                WHERE tenant_id = 'tenant-1'
                """,
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                """
                UPDATE operational_impact_factors
                SET weight = 0.99
                WHERE tenant_id = 'tenant-1'
                """,
            )
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            conn.execute(
                """
                DELETE FROM operational_impact_factors
                WHERE tenant_id = 'tenant-1'
                """,
            )
