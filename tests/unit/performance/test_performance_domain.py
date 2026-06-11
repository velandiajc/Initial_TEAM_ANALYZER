from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from app.application.performance.services import CoachingLineageService
from app.domain.performance.entities import (
    CoachingCommitment,
    CoachingNote,
    CoachingSession,
    EmployeePerformanceTimelineEvent,
    PerformanceOpportunity,
)
from app.domain.performance.value_objects import (
    CoachingNoteVisibility,
    CoachingSessionStatus,
    CommitmentStatus,
    PerformanceOpportunityStatus,
    PerformanceTimelineEventSource,
)
from app.models.evidence import EvidencePack, EvidenceReviewStatus
from app.models.risk import (
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskLevel,
)


def risk_result(tenant_id="tenant-1", lineage_id="lineage-1"):
    return RiskAssessmentResult(
        tenant_id=tenant_id,
        risk_definition_id="csat-risk",
        rule_version_id="rule-1",
        rule_version_number="1.0",
        entity_type="agent",
        entity_id="agent-1",
        period_start=datetime(2026, 5, 1),
        period_end=datetime(2026, 5, 31),
        risk_score=82.5,
        risk_level=RiskLevel.HIGH,
        status=RiskAssessmentStatus.SUCCESS,
        reason="Governed CSAT risk.",
        evidence={},
        source_reference="survey:2026-05",
        assessment_run_id="run-1",
        risk_definition_version="2.0",
        kpi_result_ids=["kpi-result-1"],
        formula_versions=[{"formula_version_id": "formula-1"}],
        source_record_ids=["source-1"],
        source_validation_lineage={"status": ["valid"]},
        lineage_id=lineage_id,
        result_id="risk-result-1",
    )


def evidence_pack(
    tenant_id="tenant-1",
    review_status=EvidenceReviewStatus.ACCEPTED,
):
    return EvidencePack(
        evidence_pack_id="pack-1",
        tenant_id=tenant_id,
        agent_id="agent-1",
        review_status=review_status,
        evidence_artifacts=["artifact-1"],
        supporting_kpis=["kpi-result-1"],
        supporting_risks=["risk-result-1"],
    )


def session():
    return CoachingSession(
        coaching_session_id="session-1",
        tenant_id="tenant-1",
        employee_id="agent-1",
        session_owner_id="manager-1",
        performance_opportunity_id="opportunity-1",
        evidence_pack_id="pack-1",
        evidence_version_snapshot="2026-06-11T12:00:00+00:00",
        evidence_artifact_ids_snapshot=("artifact-1",),
        risk_result_id="risk-result-1",
        risk_score_snapshot=82.5,
        risk_level_snapshot="HIGH",
        risk_classification_snapshot="csat-risk",
        risk_definition_version="2.0",
        risk_rule_version="1.0",
        coaching_version="1.0",
        lineage_id="lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
    )


def test_required_enum_vocabulary():
    assert [item.value for item in CoachingSessionStatus] == [
        "DRAFT",
        "OPEN",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
    ]
    assert [item.value for item in PerformanceOpportunityStatus] == [
        "IDENTIFIED",
        "UNDER_REVIEW",
        "ACCEPTED",
        "CLOSED",
        "CANCELLED",
    ]
    assert [item.value for item in CommitmentStatus] == [
        "OPEN",
        "IN_PROGRESS",
        "COMPLETED",
        "MISSED",
        "CANCELLED",
    ]
    assert [item.value for item in CoachingNoteVisibility] == [
        "SHARED",
        "MANAGER_ONLY",
        "LEADERSHIP_ONLY",
    ]
    assert [item.value for item in PerformanceTimelineEventSource] == [
        "KPI",
        "RISK",
        "EVIDENCE",
        "COACHING",
        "FOLLOWUP",
        "COMMITMENT",
        "MANUAL",
    ]


def test_lineage_builds_immutable_risk_and_evidence_snapshot():
    snapshot = CoachingLineageService().build_snapshot(
        "tenant-1",
        "agent-1",
        evidence_pack(),
        risk_result(),
    )

    assert snapshot.risk_result_id == "risk-result-1"
    assert snapshot.risk_score_snapshot == 82.5
    assert snapshot.risk_level_snapshot == "HIGH"
    assert snapshot.risk_definition_version == "2.0"
    assert snapshot.risk_rule_version == "1.0"
    assert snapshot.evidence_pack_id == "pack-1"
    assert snapshot.evidence_artifact_ids_snapshot == ("artifact-1",)


@pytest.mark.parametrize(
    ("pack", "risk", "message"),
    [
        (
            evidence_pack("tenant-2"),
            risk_result(),
            "Evidence pack tenant",
        ),
        (
            evidence_pack(),
            risk_result("tenant-2"),
            "Risk result tenant",
        ),
        (
            evidence_pack(
                review_status=EvidenceReviewStatus.SUGGESTED
            ),
            risk_result(),
            "must be accepted",
        ),
    ],
)
def test_lineage_rejects_untrusted_or_cross_tenant_inputs(
    pack,
    risk,
    message,
):
    error = PermissionError if "tenant" in message else ValueError
    with pytest.raises(error, match=message):
        CoachingLineageService().validate_lineage(
            "tenant-1",
            "agent-1",
            pack,
            risk,
        )


def test_session_snapshots_are_frozen_and_status_returns_new_record():
    original = session()
    updated = original.with_status(CoachingSessionStatus.OPEN, "manager-2")

    assert original.status == CoachingSessionStatus.DRAFT
    assert updated.status == CoachingSessionStatus.OPEN
    assert updated.risk_score_snapshot == original.risk_score_snapshot
    with pytest.raises(FrozenInstanceError):
        original.risk_score_snapshot = 1


def test_invalid_terminal_session_transition_is_rejected():
    completed = (
        session()
        .with_status(CoachingSessionStatus.OPEN, "manager-1")
        .with_status(CoachingSessionStatus.COMPLETED, "manager-1")
    )
    with pytest.raises(ValueError, match="Invalid coaching session transition"):
        completed.with_status(CoachingSessionStatus.OPEN, "manager-1")


def test_commitment_transitions_preserve_original_record():
    commitment = CoachingCommitment(
        commitment_id="commitment-1",
        tenant_id="tenant-1",
        session_id="session-1",
        employee_id="agent-1",
        description="Use the approved call control procedure.",
        target_date=date(2026, 6, 30),
        lineage_id="lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
    )
    completed = commitment.with_status(
        CommitmentStatus.COMPLETED,
        "manager-1",
    )

    assert commitment.status == CommitmentStatus.OPEN
    assert completed.status == CommitmentStatus.COMPLETED
    with pytest.raises(ValueError, match="Invalid commitment transition"):
        completed.with_status(CommitmentStatus.IN_PROGRESS, "manager-1")


def test_note_visibility_is_immutable():
    note = CoachingNote(
        note_id="note-1",
        tenant_id="tenant-1",
        session_id="session-1",
        visibility_level=CoachingNoteVisibility.MANAGER_ONLY,
        content_reference="notes/manager/note-1",
        lineage_id="lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
    )
    with pytest.raises(FrozenInstanceError):
        note.visibility_level = CoachingNoteVisibility.SHARED


@pytest.mark.parametrize(
    "field_name",
    ["lineage_id", "evidence_pack_id", "risk_result_id"],
)
def test_opportunity_rejects_missing_governance_reference(field_name):
    values = {
        "opportunity_id": "opportunity-1",
        "tenant_id": "tenant-1",
        "employee_id": "agent-1",
        "opportunity_type": "CSAT",
        "business_reason": "Governed performance opportunity.",
        "evidence_pack_id": "pack-1",
        "risk_result_id": "risk-result-1",
        "owner": "manager-1",
        "lineage_id": "lineage-1",
        "created_by": "manager-1",
        "updated_by": "manager-1",
    }
    values[field_name] = ""
    with pytest.raises(ValueError, match=field_name):
        PerformanceOpportunity(**values)


def test_timeline_requires_lineage_and_source_reference():
    with pytest.raises(ValueError, match="lineage_id"):
        EmployeePerformanceTimelineEvent(
            timeline_event_id="event-1",
            tenant_id="tenant-1",
            employee_id="agent-1",
            event_type="COACHING_SESSION_CREATED",
            event_source=PerformanceTimelineEventSource.COACHING,
            source_entity_id="session-1",
            lineage_id="",
            created_by="manager-1",
            updated_by="manager-1",
        )
