from app.domain.performance.value_objects import CoachingNoteVisibility
from tests.integration.workspace.support import build_workspace_stack
from tests.unit.workspace.support import (
    commitment,
    context,
    employee_request,
    followup,
    impact_assessment,
    impact_event,
    kpi_result,
    note,
    notes,
    opportunity,
    performance_event,
    priority_assessment,
    risk_result,
    session,
    team_request,
    workspace_request,
)


def test_workspace_services_build_all_supervisor_views_and_audits(tmp_path):
    stack = build_workspace_stack(tmp_path)
    ctx = context()
    priority = priority_assessment()
    impact = impact_assessment()
    risk = risk_result()
    kpi = kpi_result()
    coaching_session = session()
    open_commitment = commitment()
    scheduled_followup = followup()

    command = stack["workspace"].build_command_center(
        ctx,
        workspace_request(),
        (priority,),
        (impact,),
        employee_display_names={"employee-1": "Employee One"},
        risk_drivers={"risk-result-1": ("qa-score",)},
        commitments=(open_commitment,),
        followups=(scheduled_followup,),
        coaching_sessions=(coaching_session,),
    )
    team = stack["workspace"].build_team_performance(
        ctx,
        team_request(),
        (priority,),
        (impact,),
        kpi_results=(kpi,),
        risk_results=(risk,),
        commitments=(open_commitment,),
        coaching_sessions=(coaching_session,),
        employee_display_names={"employee-1": "Employee One"},
    )
    profile = stack["workspace"].build_agent_profile(
        ctx,
        employee_request(),
        kpi_results=(kpi,),
        risk_results=(risk,),
        impact_assessments=(impact,),
        priority_assessments=(priority,),
        coaching_sessions=(coaching_session,),
        commitments=(open_commitment,),
        evidence_references=(
            "evidence:accepted-1",
            "transcript:restricted-1",
        ),
        timeline_preview=({
            "event_type": "KPI_CHANGED",
            "customer_comments": "restricted",
        },),
        employee_display_name="Employee One",
    )
    timeline = stack["workspace"].build_employee_timeline(
        ctx,
        employee_request(),
        performance_events=(performance_event(),),
        operational_impact_events=(impact_event(),),
        risk_results=(risk,),
        impact_assessments=(impact,),
        priority_assessments=(priority,),
    )
    coaching = stack["workspace"].build_coaching_workspace(
        ctx,
        employee_request(),
        priority,
        impact,
        opportunities=(opportunity(),),
        coaching_sessions=(coaching_session,),
        commitments=(open_commitment,),
        followups=(scheduled_followup,),
        notes=notes(),
        evidence_references=("evidence:accepted-1",),
    )

    assert command.immediate_intervention_count == 1
    assert command.open_commitments_count == 1
    assert command.overdue_followups_count == 1
    assert team.risk_distribution["high"] == 1
    assert team.impact_distribution["HIGH"] == 1
    assert profile.priority_summary["priority_score"] == 88
    assert profile.evidence_references == (
        "evidence:accepted-1",
        "evidence-pack-1",
        "artifact-1",
    )
    assert "customer_comments" not in profile.timeline_preview[0]
    assert timeline.event_count == 5
    assert coaching.private_note_access is True
    assert [
        item["visibility_level"]
        for item in coaching.coaching_context["visible_notes"]
    ] == ["SHARED", "MANAGER_ONLY"]

    actions = {
        event.action
        for event in stack["audit_service"].list_events(ctx)
    }
    assert {
        "SUPERVISOR_WORKSPACE_VIEWED",
        "SUPERVISOR_PRIORITY_QUEUE_VIEWED",
        "TEAM_PERFORMANCE_VIEWED",
        "AGENT_PROFILE_VIEWED",
        "EMPLOYEE_TIMELINE_VIEWED",
        "COACHING_WORKSPACE_VIEWED",
        "RESTRICTED_WORKSPACE_DATA_SUPPRESSED",
        "LEADERSHIP_NOTE_ACCESS_DENIED",
    } <= actions


def test_workspace_layer_does_not_recalculate_or_persist_read_models(tmp_path):
    stack = build_workspace_stack(tmp_path)
    ctx = context()
    priority = priority_assessment(score=88)
    impact = impact_assessment(score=68)
    risk = risk_result()

    queue = stack["priority_queue"].build_priority_queue(
        ctx,
        workspace_request(),
        (priority,),
        (impact,),
    )
    profile = stack["profile"].build_agent_profile(
        ctx,
        employee_request(),
        risk_results=(risk,),
        impact_assessments=(impact,),
        priority_assessments=(priority,),
    )

    assert queue[0].priority_score == priority.priority_score
    assert queue[0].risk_score == priority.risk_score_snapshot
    assert queue[0].impact_score == priority.impact_score_snapshot
    assert profile.risk_summary["risk_score"] == risk.risk_score
    assert profile.impact_summary["impact_score"] == impact.impact_score

    with stack["database"].connect() as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert not {
        name for name in table_names
        if "workspace" in name.lower()
    }


def test_coaching_note_visibility_changes_only_metadata_exposure(tmp_path):
    stack = build_workspace_stack(tmp_path)
    leader = context(
        role="leadership",
        user_id="leader-1",
    )
    request = employee_request()
    request = type(request)(
        tenant_id=request.tenant_id,
        requester_id="leader-1",
        supervisor_id="leader-1",
        employee_id=request.employee_id,
    )

    view = stack["coaching"].build_coaching_workspace(
        leader,
        request,
        priority_assessment(),
        impact_assessment(),
        coaching_sessions=(session(),),
        notes=(
            note(CoachingNoteVisibility.MANAGER_ONLY, "manager-note"),
            note(
                CoachingNoteVisibility.LEADERSHIP_ONLY,
                "leadership-note",
            ),
        ),
    )

    assert {
        item["visibility_level"]
        for item in view.coaching_context["visible_notes"]
    } == {"MANAGER_ONLY", "LEADERSHIP_ONLY"}
    assert all(
        "content_reference" not in item
        for item in view.coaching_context["visible_notes"]
    )
