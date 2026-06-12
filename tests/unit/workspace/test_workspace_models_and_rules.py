from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from app.application.workspace.dto import WorkspaceFilters
from app.application.workspace.read_models import (
    AgentPerformanceProfileView,
    CoachingWorkspaceView,
    EmployeePerformanceTimelineView,
    SupervisorCommandCenterView,
    SupervisorPriorityQueueItem,
    TeamPerformanceView,
)
from app.application.workspace.rules import (
    WorkspaceLineageRules,
    WorkspaceSuppressionRules,
    WorkspaceVisibilityRules,
)
from app.application.workspace.services import (
    SupervisorPriorityQueueService,
    SupervisorTimelineService,
    SupervisorWorkspaceService,
)
from app.core.permissions import GovernanceRole
from app.domain.operational_impact.value_objects import PriorityLevel
from app.domain.performance.value_objects import CoachingNoteVisibility
from tests.unit.workspace.support import (
    RecordingAuditService,
    context,
    employee_request,
    impact_assessment,
    priority_assessment,
    risk_result,
    team_request,
    workspace_request,
)


def queue_item():
    return SupervisorPriorityQueueItem(
        tenant_id="tenant-1",
        employee_id="employee-1",
        employee_display_name="Employee One",
        priority_level="COACH",
        priority_score=60,
        risk_score=55,
        impact_score=50,
        risk_drivers=("qa-score",),
        impact_drivers=("factor-qa",),
        priority_reason="Governed reason.",
        recommended_action_type="COACH",
        last_coaching_date=None,
        open_commitments_count=0,
        lineage_id="lineage-1",
        lineage_references=("priority:1",),
    )


def test_all_read_models_construct_as_immutable_disposable_views():
    item = queue_item()
    command = SupervisorCommandCenterView(
        tenant_id="tenant-1",
        supervisor_id="manager-1",
        priority_queue=(item,),
        team_health_summary={"employee_count": 1},
        immediate_intervention_count=0,
        escalate_count=0,
        coach_count=1,
        monitor_count=0,
        top_operational_impact_drivers=("factor-qa",),
        open_commitments_count=0,
        overdue_followups_count=0,
        lineage_references=("priority:1",),
    )
    team = TeamPerformanceView(
        tenant_id="tenant-1",
        team_id="team-1",
        supervisor_id="manager-1",
        employees=({"employee_id": "employee-1"},),
        risk_distribution={"high": 1},
        impact_distribution={"HIGH": 1},
        priority_distribution={"COACH": 1},
        team_kpi_summary=(),
        team_coaching_summary={"session_count": 0},
        lineage_references=("priority:1",),
    )
    profile = AgentPerformanceProfileView(
        tenant_id="tenant-1",
        employee_id="employee-1",
        employee_display_name="Employee One",
        risk_summary={"risk_score": 55},
        impact_summary={"impact_score": 50},
        priority_summary={"priority_score": 60},
        kpi_summary=(),
        evidence_references=(),
        coaching_summary={},
        open_commitments=(),
        timeline_preview=(),
        lineage_references=("priority:1",),
    )
    timeline = EmployeePerformanceTimelineView(
        tenant_id="tenant-1",
        employee_id="employee-1",
        events=(),
        event_count=99,
        date_range_start=None,
        date_range_end=None,
        lineage_references=("workspace_status:incomplete:no_events",),
    )
    coaching = CoachingWorkspaceView(
        tenant_id="tenant-1",
        employee_id="employee-1",
        coaching_context={},
        linked_priority_assessment={},
        linked_impact_assessment={},
        linked_evidence_references=(),
        opportunities=(),
        commitments=(),
        followups=(),
        private_note_access=False,
        lineage_references=("priority:1",),
    )

    assert command.priority_queue == (item,)
    assert team.risk_distribution["high"] == 1
    assert profile.risk_summary["risk_score"] == 55
    assert timeline.event_count == 0
    assert coaching.private_note_access is False
    with pytest.raises(FrozenInstanceError):
        item.priority_score = 1
    with pytest.raises(TypeError):
        command.team_health_summary["employee_count"] = 2


def test_priority_queue_preserves_scores_sorts_and_groups_without_calculation():
    audit = RecordingAuditService()
    service = SupervisorPriorityQueueService(audit)
    priorities = (
        priority_assessment(
            employee_id="employee-2",
            score=45,
            level=PriorityLevel.COACH,
        ),
        priority_assessment(score=88),
    )
    impacts = (
        impact_assessment(employee_id="employee-1"),
        impact_assessment(employee_id="employee-2"),
    )

    items = service.build_priority_queue(
        context(),
        team_request(employee_ids=("employee-1", "employee-2")),
        priorities,
        impacts,
    )
    grouped = service.group_by_priority_level(items)

    assert [item.priority_score for item in items] == [88, 45]
    assert items[0].risk_score == 82.5
    assert items[0].impact_score == 68
    assert items[0].recommended_action_type == items[0].priority_level
    assert grouped["IMMEDIATE_INTERVENTION"] == (items[0],)
    assert grouped["COACH"] == (items[1],)


def test_suppression_removes_restricted_data_and_redacts_pci():
    rules = WorkspaceSuppressionRules()
    value = {
        "customer_comments": "do not expose",
        "call_transcript": "do not expose",
        "recording_url": "do not expose",
        "private_note": "do not expose",
        "leadership_note": "do not expose",
        "safe": "PAN 4111 1111 1111 1111 and CVV: 123",
        "references": ["customer:123", "evidence:abc"],
    }

    sanitized, reasons = rules.suppress(value)

    assert set(sanitized) == {"safe", "references"}
    assert "[REDACTED PAN]" in sanitized["safe"]
    assert "[REDACTED CVV]" in sanitized["safe"]
    assert sanitized["references"][0] == "[SUPPRESSED]"
    assert {"PCI_REDACTED", "RESTRICTED_FIELD"} <= set(reasons)


def test_visibility_denies_by_default_and_keeps_sensitive_permissions_separate():
    rules = WorkspaceVisibilityRules()
    manager = context()
    leader = context(
        GovernanceRole.LEADERSHIP,
        user_id="leader-1",
    )
    coach = context(GovernanceRole.PERFORMANCE_COACH)

    assert rules.can_view_note(
        manager,
        CoachingNoteVisibility.MANAGER_ONLY,
    )
    assert not rules.can_view_note(
        manager,
        CoachingNoteVisibility.LEADERSHIP_ONLY,
    )
    assert rules.can_view_note(
        leader,
        CoachingNoteVisibility.LEADERSHIP_ONLY,
    )
    assert not rules.can_view_note(
        coach,
        CoachingNoteVisibility.MANAGER_ONLY,
    )


def test_lineage_preserves_priority_impact_risk_kpi_and_versions():
    references = WorkspaceLineageRules().priority_references(
        priority_assessment(),
        impact_assessment(),
    )

    assert "risk_result:risk-result-1" in references
    assert "risk_definition_version:2.0" in references
    assert "risk_rule_version:1.0" in references
    assert "impact_definition_version:3.0" in references
    assert "impact_factor_version:factor-qa:2.0" in references
    assert "impact_threshold_version:factor-qa:4.0" in references
    assert "kpi_result:kpi-result-1" in references


def test_empty_command_center_and_timeline_are_explicitly_incomplete():
    audit = RecordingAuditService()
    queue = SupervisorPriorityQueueService(audit)
    workspace = SupervisorWorkspaceService(audit, queue)
    timeline = SupervisorTimelineService(audit)

    command = workspace.build_command_center(
        context(),
        workspace_request(),
        (),
        (),
    )
    event_view = timeline.build_timeline(
        context(),
        employee_request(),
    )

    assert command.priority_queue == ()
    assert command.team_health_summary["lineage_complete"] is False
    assert command.lineage_references == (
        "workspace_status:incomplete:no_results",
    )
    assert event_view.events == ()
    assert event_view.lineage_references == (
        "workspace_status:incomplete:no_events",
    )


def test_team_risk_distribution_uses_authoritative_risk_level():
    audit = RecordingAuditService()
    queue = SupervisorPriorityQueueService(audit)
    workspace = SupervisorWorkspaceService(audit, queue)

    view = workspace.build_team_performance(
        context(),
        team_request(),
        (priority_assessment(),),
        (impact_assessment(),),
        risk_results=(risk_result(),),
    )

    assert dict(view.risk_distribution) == {"high": 1}


def test_invalid_tenant_and_unauthorized_access_are_rejected_and_audited():
    audit = RecordingAuditService()
    queue = SupervisorPriorityQueueService(audit)

    with pytest.raises(PermissionError, match="tenant"):
        queue.build_priority_queue(
            context(),
            workspace_request("tenant-2"),
            (),
            (),
        )
    with pytest.raises(PermissionError, match="not allowed"):
        queue.build_priority_queue(
            context(GovernanceRole.PERFORMANCE_COACH),
            workspace_request(),
            (),
            (),
        )

    actions = [event["action"] for event in audit.events]
    assert "CROSS_TENANT_WORKSPACE_ACCESS_DENIED" in actions
    assert "SUPERVISOR_WORKSPACE_ACCESS_DENIED" in actions


def test_workspace_filter_rejects_invalid_date_range():
    with pytest.raises(ValueError, match="date_range_start"):
        WorkspaceFilters(
            date_range_start=datetime(2026, 6, 2),
            date_range_end=datetime(2026, 6, 1),
        )
