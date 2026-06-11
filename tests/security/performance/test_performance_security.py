import json
from datetime import date

import pytest

from app.core.permissions import GovernanceRole
from app.domain.performance.value_objects import CoachingNoteVisibility
from tests.integration.performance.support import (
    build_stack,
    context,
    create_session_foundation,
    evidence_pack,
    risk_result,
)


def test_unauthorized_session_creation_is_rejected_and_audited(tmp_path):
    stack = build_stack(tmp_path)
    unauthorized = context(role=None, user_id="viewer-1")

    with pytest.raises(PermissionError, match="create_coaching_session"):
        stack["services"]["opportunities"].create_opportunity(
            unauthorized,
            "agent-1",
            "CSAT",
            "Governed reason.",
            evidence_pack(),
            risk_result(),
        )

    actions = [
        event.action
        for event in stack["audit_repository"].list_events(unauthorized)
    ]
    assert actions == ["COACHING_ACCESS_DENIED"]


def test_cross_tenant_writes_are_rejected(tmp_path):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, opportunity, session = create_session_foundation(stack, manager)
    other_tenant = context(tenant_id="tenant-2")

    with pytest.raises(PermissionError, match="tenant-scoped"):
        stack["repositories"]["opportunities"].save(
            other_tenant,
            opportunity,
        )
    with pytest.raises(PermissionError, match="tenant-scoped"):
        stack["repositories"]["sessions"].save(other_tenant, session)


def test_cross_tenant_reads_do_not_return_performance_history(tmp_path):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, _, session = create_session_foundation(stack, manager)
    commitment = stack["services"]["commitments"].create_commitment(
        manager,
        session.coaching_session_id,
        "Use the approved call control procedure.",
        date(2026, 6, 30),
        commitment_id="commitment-1",
    )
    followup = stack["services"]["followups"].create_followup(
        manager,
        session.coaching_session_id,
        commitment.commitment_id,
        manager.user_id,
        followup_id="followup-1",
    )
    note = stack["services"]["notes"].create_note(
        manager,
        session.coaching_session_id,
        CoachingNoteVisibility.MANAGER_ONLY,
        "secure-reference://manager/note-1",
        note_id="note-1",
    )
    other_tenant = context(tenant_id="tenant-2")

    assert stack["repositories"]["sessions"].get_session(
        other_tenant,
        "session-1",
    ) is None
    assert stack["repositories"]["commitments"].get_by_id(
        other_tenant,
        commitment.commitment_id,
    ) is None
    assert stack["repositories"]["followups"].get_by_id(
        other_tenant,
        followup.followup_id,
    ) is None
    assert stack["repositories"]["notes"].get_note(
        other_tenant,
        note.note_id,
    ) is None
    assert stack["services"]["timeline"].get_timeline(
        other_tenant,
        "agent-1",
    ) == []
    assert stack["audit_repository"].list_events(other_tenant) == []


def test_unauthorized_commitment_followup_and_timeline_access_rejected(
    tmp_path,
):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, _, session = create_session_foundation(stack, manager)
    unauthorized = context(role=None, user_id="viewer-1")

    with pytest.raises(PermissionError, match="create_commitment"):
        stack["services"]["commitments"].create_commitment(
            unauthorized,
            session.coaching_session_id,
            "Unauthorized commitment.",
            date(2026, 6, 30),
        )
    with pytest.raises(PermissionError, match="create_followup"):
        stack["services"]["followups"].create_followup(
            unauthorized,
            session.coaching_session_id,
            "commitment-1",
            unauthorized.user_id,
        )
    with pytest.raises(PermissionError, match="view_performance_timeline"):
        stack["services"]["timeline"].get_timeline(
            unauthorized,
            "agent-1",
        )


def test_private_note_permission_is_independent_from_session_access(tmp_path):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, _, session = create_session_foundation(stack, manager)
    note = stack["services"]["notes"].create_note(
        manager,
        session.coaching_session_id,
        CoachingNoteVisibility.MANAGER_ONLY,
        "secure-reference://manager/note-1",
        note_id="note-1",
    )
    coach = context(
        GovernanceRole.PERFORMANCE_COACH,
        user_id="coach-1",
    )

    assert stack["services"]["sessions"].get_session(
        coach,
        session.coaching_session_id,
    )
    with pytest.raises(PermissionError, match="view_private_coaching_note"):
        stack["services"]["notes"].get_note(coach, note.note_id)


def test_leadership_only_note_rejects_manager_role(tmp_path):
    stack = build_stack(tmp_path)
    admin = context(GovernanceRole.GOVERNANCE_ADMIN, user_id="admin-1")
    _, _, _, session = create_session_foundation(stack, admin)
    note = stack["services"]["notes"].create_note(
        admin,
        session.coaching_session_id,
        CoachingNoteVisibility.LEADERSHIP_ONLY,
        "secure-reference://leadership/note-1",
        note_id="note-1",
    )
    manager = context()
    leadership = context(GovernanceRole.LEADERSHIP, user_id="leader-1")

    with pytest.raises(PermissionError, match="LEADERSHIP_ONLY"):
        stack["services"]["notes"].get_note(manager, note.note_id)
    assert stack["services"]["notes"].get_note(
        leadership,
        note.note_id,
    ).note_id == note.note_id


def test_private_note_content_is_absent_from_audit_and_timeline(tmp_path):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, _, session = create_session_foundation(stack, manager)
    secret_reference = "secure-reference://private/highly-sensitive-note"
    note = stack["services"]["notes"].create_note(
        manager,
        session.coaching_session_id,
        CoachingNoteVisibility.MANAGER_ONLY,
        secret_reference,
        note_id="note-1",
    )
    stack["services"]["notes"].get_note(manager, note.note_id)

    audit_payload = json.dumps([
        event.metadata
        for event in stack["audit_repository"].list_events(manager)
    ])
    timeline_payload = json.dumps([
        event.__dict__
        for event in stack["services"]["timeline"].get_timeline(
            manager,
            "agent-1",
        )
    ], default=str)

    assert secret_reference not in audit_payload
    assert secret_reference not in timeline_payload


def test_note_visibility_and_content_are_historically_immutable(tmp_path):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, _, session = create_session_foundation(stack, manager)
    note = stack["services"]["notes"].create_note(
        manager,
        session.coaching_session_id,
        CoachingNoteVisibility.MANAGER_ONLY,
        "secure-reference://manager/note-1",
        note_id="note-1",
    )
    object.__setattr__(note, "visibility_level", CoachingNoteVisibility.SHARED)

    with pytest.raises(PermissionError, match="immutable"):
        stack["repositories"]["notes"].save(manager, note)


def test_private_note_access_generates_required_audit_event(tmp_path):
    stack = build_stack(tmp_path)
    manager = context()
    _, _, _, session = create_session_foundation(stack, manager)
    note = stack["services"]["notes"].create_note(
        manager,
        session.coaching_session_id,
        CoachingNoteVisibility.MANAGER_ONLY,
        "secure-reference://manager/note-1",
        note_id="note-1",
    )

    stack["services"]["notes"].get_note(manager, note.note_id)
    assert "PRIVATE_NOTE_VIEWED" in [
        event.action
        for event in stack["audit_repository"].list_events(manager)
    ]
