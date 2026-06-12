from dataclasses import replace
import json

import pytest

from app.core.permissions import GovernanceRole
from app.domain.performance.value_objects import CoachingNoteVisibility
from tests.integration.workspace.support import build_workspace_stack
from tests.unit.workspace.support import (
    context,
    employee_request,
    impact_assessment,
    kpi_result,
    note,
    priority_assessment,
    risk_result,
    session,
    team_request,
    workspace_request,
)


def cross_tenant_calls(stack):
    ctx = context()
    request = workspace_request("tenant-2")
    employee = employee_request("tenant-2")
    team = team_request("tenant-2")
    return (
        lambda: stack["priority_queue"].build_priority_queue(
            ctx,
            request,
            (),
            (),
        ),
        lambda: stack["workspace"].build_command_center(
            ctx,
            request,
            (),
            (),
        ),
        lambda: stack["workspace"].build_team_performance(
            ctx,
            team,
            (),
            (),
        ),
        lambda: stack["profile"].build_agent_profile(
            ctx,
            employee,
        ),
        lambda: stack["timeline"].build_timeline(
            ctx,
            employee,
        ),
        lambda: stack["coaching"].build_coaching_workspace(
            ctx,
            employee,
            priority_assessment(),
            impact_assessment(),
        ),
    )


def test_cross_tenant_access_is_rejected_for_every_workspace_view(tmp_path):
    stack = build_workspace_stack(tmp_path)

    for call in cross_tenant_calls(stack):
        with pytest.raises(PermissionError, match="tenant"):
            call()

    events = stack["audit_service"].list_events(context())
    denied = [
        event
        for event in events
        if event.action == "CROSS_TENANT_WORKSPACE_ACCESS_DENIED"
    ]
    assert len(denied) == 6


def test_cross_tenant_governed_records_are_rejected(tmp_path):
    stack = build_workspace_stack(tmp_path)

    with pytest.raises(PermissionError, match="tenant"):
        stack["priority_queue"].build_priority_queue(
            context(),
            workspace_request(),
            (priority_assessment(tenant_id="tenant-2"),),
            (impact_assessment(tenant_id="tenant-2"),),
        )

    assert any(
        event.action == "CROSS_TENANT_WORKSPACE_ACCESS_DENIED"
        for event in stack["audit_service"].list_events(context())
    )


@pytest.mark.parametrize(
    "service_name",
    (
        "priority_queue",
        "profile",
        "timeline",
        "coaching",
    ),
)
def test_unauthorized_workspace_access_is_denied_and_audited(
    tmp_path,
    service_name,
):
    stack = build_workspace_stack(tmp_path)
    ctx = context(GovernanceRole.PERFORMANCE_COACH)
    if service_name == "priority_queue":
        call = lambda: stack[service_name].build_priority_queue(
            ctx,
            workspace_request(),
            (),
            (),
        )
    elif service_name == "profile":
        call = lambda: stack[service_name].build_agent_profile(
            ctx,
            employee_request(),
        )
    elif service_name == "timeline":
        call = lambda: stack[service_name].build_timeline(
            ctx,
            employee_request(),
        )
    else:
        call = lambda: stack[service_name].build_coaching_workspace(
            ctx,
            employee_request(),
            priority_assessment(),
            impact_assessment(),
        )

    with pytest.raises(PermissionError, match="not allowed"):
        call()

    assert any(
        event.action == "SUPERVISOR_WORKSPACE_ACCESS_DENIED"
        for event in stack["audit_service"].list_events(ctx)
    )


def test_restricted_data_is_suppressed_from_all_workspace_outputs(tmp_path):
    stack = build_workspace_stack(tmp_path)
    sensitive_reason = (
        "customer:123 transcript:call-1 recording:call-1 "
        "PAN 4111 1111 1111 1111 CVV: 123"
    )
    priority = priority_assessment(reason=sensitive_reason)
    impact = impact_assessment()
    ctx = context()

    queue = stack["priority_queue"].build_priority_queue(
        ctx,
        workspace_request(),
        (priority,),
        (impact,),
        employee_display_names={
            "employee-1": "Employee 4111 1111 1111 1111",
        },
        risk_drivers={
            "risk-result-1": (
                "customer:123",
                "transcript:call-1",
                "governed-driver",
            ),
        },
        coaching_sessions=(
            replace(
                session(),
                evidence_artifact_ids_snapshot=(
                    "transcript:call-1",
                    "artifact-1",
                ),
            ),
        ),
    )
    profile = stack["profile"].build_agent_profile(
        ctx,
        employee_request(),
        kpi_results=(kpi_result(),),
        risk_results=(risk_result(),),
        impact_assessments=(impact,),
        priority_assessments=(priority,),
        coaching_sessions=(session(),),
        evidence_references=(
            "customer:123",
            "transcript:call-1",
            "recording:call-1",
            "evidence:accepted",
        ),
        timeline_preview=({
            "customer_comments": "restricted",
            "raw_source_payload": "restricted",
            "safe": "CVV: 123",
        },),
    )
    coaching = stack["coaching"].build_coaching_workspace(
        ctx,
        employee_request(),
        priority,
        impact,
        coaching_sessions=(session(),),
        notes=(
            note(CoachingNoteVisibility.SHARED, "shared-note"),
            note(
                CoachingNoteVisibility.LEADERSHIP_ONLY,
                "leadership-note",
            ),
        ),
        evidence_references=(
            "customer:123",
            "recording:call-1",
            "evidence:accepted",
        ),
    )

    rendered = json.dumps(
        {
            "queue": {
                "display": queue[0].employee_display_name,
                "reason": queue[0].priority_reason,
                "drivers": queue[0].risk_drivers,
            },
            "profile": {
                "evidence": profile.evidence_references,
                "timeline": [
                    dict(item) for item in profile.timeline_preview
                ],
            },
            "coaching": {
                "context": dict(coaching.coaching_context),
                "evidence": coaching.linked_evidence_references,
            },
        },
        default=str,
    ).lower()

    for forbidden in (
        "4111 1111 1111 1111",
        "cvv: 123",
        "customer:123",
        "transcript:call-1",
        "recording:call-1",
        "customer_comments",
        "raw_source_payload",
        "content_reference",
    ):
        assert forbidden not in rendered
    assert queue[0].risk_drivers == ("governed-driver",)
    assert "evidence_reference:transcript:call-1" not in (
        queue[0].lineage_references
    )
    assert "evidence_reference:artifact-1" in queue[0].lineage_references
    assert profile.evidence_references == (
        "evidence:accepted",
        "evidence-pack-1",
        "artifact-1",
    )


def test_audit_metadata_is_sanitized_and_tenant_filtered(tmp_path):
    stack = build_workspace_stack(tmp_path)
    ctx = context()
    priority = priority_assessment(
        reason="PAN 4111 1111 1111 1111 CVV: 123",
    )

    stack["priority_queue"].build_priority_queue(
        ctx,
        workspace_request(),
        (priority,),
        (impact_assessment(),),
        risk_drivers={"risk-result-1": ("transcript:restricted",)},
    )
    events = stack["audit_service"].list_events(ctx)
    rendered = json.dumps([
        event.metadata for event in events
    ]).lower()

    for forbidden in (
        "4111 1111 1111 1111",
        "cvv: 123",
        "transcript:restricted",
        "priority_reason",
        "customer",
        "payload",
    ):
        assert forbidden not in rendered
    assert stack["audit_service"].list_events(
        context(tenant_id="tenant-2"),
    ) == []


def test_workspace_access_does_not_grant_leadership_note_access(tmp_path):
    stack = build_workspace_stack(tmp_path)
    ctx = context()

    view = stack["coaching"].build_coaching_workspace(
        ctx,
        employee_request(),
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

    assert [
        item["visibility_level"]
        for item in view.coaching_context["visible_notes"]
    ] == ["MANAGER_ONLY"]
    assert any(
        event.action == "LEADERSHIP_NOTE_ACCESS_DENIED"
        for event in stack["audit_service"].list_events(ctx)
    )
