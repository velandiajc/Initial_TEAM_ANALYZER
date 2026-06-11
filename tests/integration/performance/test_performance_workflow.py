import sqlite3
from datetime import date

import pytest

from app.domain.performance.value_objects import (
    CoachingNoteVisibility,
    CoachingSessionStatus,
    CommitmentStatus,
    FollowUpStatus,
)
from tests.integration.performance.support import (
    build_stack,
    context,
    create_session_foundation,
)


def test_full_governed_performance_management_flow(tmp_path):
    stack = build_stack(tmp_path)
    ctx = context()
    _, _, _, session = create_session_foundation(stack, ctx)

    session = stack["services"]["sessions"].update_session(
        ctx,
        session.coaching_session_id,
        CoachingSessionStatus.OPEN,
    )
    commitment = stack["services"]["commitments"].create_commitment(
        ctx,
        session.coaching_session_id,
        "Use the approved call control procedure.",
        date(2026, 6, 30),
        commitment_id="commitment-1",
    )
    commitment = stack["services"]["commitments"].update_commitment_status(
        ctx,
        commitment.commitment_id,
        CommitmentStatus.COMPLETED,
    )
    followup = stack["services"]["followups"].create_followup(
        ctx,
        session.coaching_session_id,
        commitment.commitment_id,
        ctx.user_id,
        followup_id="followup-1",
    )
    followup = stack["services"]["followups"].complete_followup(
        ctx,
        followup.followup_id,
        FollowUpStatus.COMPLETED,
        "Commitment was observed and completed.",
    )
    note = stack["services"]["notes"].create_note(
        ctx,
        session.coaching_session_id,
        CoachingNoteVisibility.MANAGER_ONLY,
        "secure-reference://coaching/note-1",
        note_id="note-1",
    )

    persisted_session = stack["repositories"]["sessions"].get_session(
        ctx,
        session.coaching_session_id,
    )
    timeline = stack["services"]["timeline"].get_timeline(ctx, "agent-1")
    audit_actions = [
        event.action
        for event in stack["audit_repository"].list_events(ctx)
    ]

    assert persisted_session.risk_score_snapshot == 82.5
    assert persisted_session.evidence_artifact_ids_snapshot == ("artifact-1",)
    assert commitment.status == CommitmentStatus.COMPLETED
    assert followup.status == FollowUpStatus.COMPLETED
    assert note.visibility_level == CoachingNoteVisibility.MANAGER_ONLY
    assert [event.created_at for event in timeline] == sorted(
        event.created_at for event in timeline
    )
    assert "COACHING_SESSION_CREATED" in audit_actions
    assert "COMMITMENT_COMPLETED" in audit_actions
    assert "FOLLOWUP_CREATED" in audit_actions
    assert "NOTE_CREATED" in audit_actions
    assert "TIMELINE_EVENT_CREATED" in audit_actions


def test_snapshot_persistence_is_independent_of_source_object_changes(tmp_path):
    stack = build_stack(tmp_path)
    ctx = context()
    risk, pack, _, session = create_session_foundation(stack, ctx)

    risk.risk_score = 10
    risk.risk_level = "low"
    pack.evidence_artifacts.append("artifact-2")
    persisted = stack["repositories"]["sessions"].get_session(
        ctx,
        session.coaching_session_id,
    )

    assert persisted.risk_score_snapshot == 82.5
    assert persisted.risk_level_snapshot == "HIGH"
    assert persisted.evidence_artifact_ids_snapshot == ("artifact-1",)


@pytest.mark.parametrize(
    ("field_name", "message"),
    [
        ("lineage_id", "lineage_id"),
        ("evidence_pack_id", "evidence_pack_id"),
        ("risk_result_id", "risk_result_id"),
    ],
)
def test_session_persistence_fails_for_missing_governance_reference(
    tmp_path,
    field_name,
    message,
):
    stack = build_stack(tmp_path)
    ctx = context()
    _, _, _, session = create_session_foundation(stack, ctx)
    object.__setattr__(session, field_name, "")

    with pytest.raises(ValueError, match=message):
        stack["repositories"]["sessions"].save(ctx, session)


def test_database_rejects_delete_and_snapshot_mutation(tmp_path):
    stack = build_stack(tmp_path)
    ctx = context()
    _, _, _, session = create_session_foundation(stack, ctx)
    commitment = stack["services"]["commitments"].create_commitment(
        ctx,
        session.coaching_session_id,
        "Use the approved call control procedure.",
        date(2026, 6, 30),
        commitment_id="commitment-1",
    )

    with stack["database"].connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("""
                UPDATE coaching_sessions
                SET risk_score_snapshot = 1
                WHERE tenant_id = ? AND coaching_session_id = ?
            """, (ctx.tenant_id, session.coaching_session_id))
        with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
            conn.execute("""
                DELETE FROM coaching_sessions
                WHERE tenant_id = ? AND coaching_session_id = ?
            """, (ctx.tenant_id, session.coaching_session_id))
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("""
                UPDATE coaching_commitments
                SET description = 'Rewritten history'
                WHERE tenant_id = ? AND commitment_id = ?
            """, (ctx.tenant_id, commitment.commitment_id))


def test_timeline_is_append_only_and_rejects_duplicate_events(tmp_path):
    stack = build_stack(tmp_path)
    ctx = context()
    _, _, _, session = create_session_foundation(stack, ctx)
    timeline = stack["services"]["timeline"].get_timeline(ctx, "agent-1")
    event = timeline[0]

    with pytest.raises(ValueError, match="Duplicate"):
        stack["services"]["timeline"].create_timeline_event(
            ctx,
            event.employee_id,
            event.event_type,
            event.event_source,
            event.source_entity_id,
            event.lineage_id,
        )
    with stack["database"].connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute("""
                UPDATE performance_timeline_events
                SET event_type = 'CHANGED'
                WHERE tenant_id = ? AND timeline_event_id = ?
            """, (ctx.tenant_id, event.timeline_event_id))
