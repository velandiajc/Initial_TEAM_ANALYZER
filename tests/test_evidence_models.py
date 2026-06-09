from dataclasses import fields
from datetime import datetime

import pytest

from app.models.evidence import (
    EvidenceArtifact,
    EvidenceArtifactType,
    EvidenceLifecycleStatus,
    EvidenceLinkCandidate,
    EvidenceLinkConfidence,
    EvidenceLinkStatus,
    EvidencePack,
    EvidenceProcessingStatus,
    EvidenceReview,
    EvidenceReviewStatus,
    EvidenceSensitivity,
    RootCauseCategory,
)


PROHIBITED_MODEL_FIELDS = {
    "transcript_text",
    "audio_content",
    "customer_content",
    "raw_content",
    "recommendation",
    "ai_summary",
    "coaching_score",
    "auto_generated_plan",
}


def test_evidence_artifact_creation():
    artifact = EvidenceArtifact(
        artifact_id="artifact-1",
        tenant_id="tenant-1",
        artifact_type=EvidenceArtifactType.QA_AUDIT,
        source_reference="data/raw/evidence_samples/audits/audit.pdf",
        linked_record_id="qa-result-1",
        lineage_id="lineage-1",
        metadata={"month": "2026-05"},
    )

    assert artifact.artifact_id == "artifact-1"
    assert artifact.tenant_id == "tenant-1"
    assert artifact.artifact_type == EvidenceArtifactType.QA_AUDIT
    assert artifact.source_reference.endswith("audit.pdf")
    assert artifact.metadata == {"month": "2026-05"}


def test_tenant_id_is_required():
    with pytest.raises(ValueError, match="tenant_id is required"):
        EvidenceArtifact(
            artifact_id="artifact-1",
            tenant_id="",
            artifact_type=EvidenceArtifactType.QA_AUDIT,
            source_reference="local/reference.pdf",
        )


def test_recording_defaults_to_restricted():
    artifact = EvidenceArtifact(
        artifact_id="artifact-1",
        tenant_id="tenant-1",
        artifact_type=EvidenceArtifactType.RECORDING,
        source_reference="data/raw/evidence_samples/recordings/call.mp4",
    )

    assert artifact.sensitivity == EvidenceSensitivity.RESTRICTED


def test_evidence_artifact_defaults_to_discovered():
    artifact = EvidenceArtifact(
        artifact_id="artifact-1",
        tenant_id="tenant-1",
        artifact_type=EvidenceArtifactType.QA_AUDIT,
        source_reference="local/reference.pdf",
    )

    assert artifact.status == EvidenceLifecycleStatus.DISCOVERED


def test_evidence_artifact_defaults_to_metadata_only():
    artifact = EvidenceArtifact(
        artifact_id="artifact-1",
        tenant_id="tenant-1",
        artifact_type=EvidenceArtifactType.REDACTED_TRANSCRIPT,
        source_reference="local/redacted-transcript.md",
    )

    assert artifact.processing_status == EvidenceProcessingStatus.METADATA_ONLY


def test_evidence_link_candidate_defaults_to_suggested():
    candidate = EvidenceLinkCandidate(
        candidate_id="candidate-1",
        tenant_id="tenant-1",
        source_record_id="qa-result-1",
        evidence_reference="artifact-1",
        confidence_level=EvidenceLinkConfidence.MEDIUM,
    )

    assert candidate.status == EvidenceLinkStatus.SUGGESTED


def test_high_confidence_link_is_not_auto_approved():
    candidate = EvidenceLinkCandidate(
        candidate_id="candidate-1",
        tenant_id="tenant-1",
        source_record_id="qa-result-1",
        evidence_reference="artifact-1",
        confidence_level=EvidenceLinkConfidence.HIGH,
        confidence_score=0.99,
    )

    assert candidate.confidence_level == EvidenceLinkConfidence.HIGH
    assert candidate.status == EvidenceLinkStatus.SUGGESTED


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_confidence_score_validation_between_zero_and_one(score):
    with pytest.raises(ValueError, match="confidence_score must be between 0 and 1"):
        EvidenceLinkCandidate(
            candidate_id="candidate-1",
            tenant_id="tenant-1",
            source_record_id="qa-result-1",
            evidence_reference="artifact-1",
            confidence_level=EvidenceLinkConfidence.LOW,
            confidence_score=score,
        )


def test_confidence_score_accepts_bounds():
    low_candidate = EvidenceLinkCandidate(
        candidate_id="candidate-1",
        tenant_id="tenant-1",
        source_record_id="qa-result-1",
        evidence_reference="artifact-1",
        confidence_level=EvidenceLinkConfidence.LOW,
        confidence_score=0,
    )
    high_candidate = EvidenceLinkCandidate(
        candidate_id="candidate-2",
        tenant_id="tenant-1",
        source_record_id="qa-result-1",
        evidence_reference="artifact-1",
        confidence_level=EvidenceLinkConfidence.HIGH,
        confidence_score=1,
    )

    assert low_candidate.confidence_score == 0
    assert high_candidate.confidence_score == 1


def test_evidence_review_supports_human_review_traceability():
    reviewed_at = datetime(2026, 6, 9, 12, 30)
    review = EvidenceReview(
        review_id="review-1",
        tenant_id="tenant-1",
        candidate_id="candidate-1",
        artifact_id="artifact-1",
        review_status=EvidenceReviewStatus.ACCEPTED,
        reviewed_by="supervisor-1",
        reviewed_at=reviewed_at,
        review_notes="Reference approved after human review.",
        lineage_id="lineage-1",
    )

    assert review.review_status == EvidenceReviewStatus.ACCEPTED
    assert review.reviewed_by == "supervisor-1"
    assert review.reviewed_at == reviewed_at
    assert review.lineage_id == "lineage-1"


def test_evidence_pack_requires_human_review_required_true():
    with pytest.raises(ValueError, match="human_review_required"):
        EvidencePack(
            evidence_pack_id="pack-1",
            tenant_id="tenant-1",
            human_review_required=False,
        )


def test_evidence_pack_defaults_to_suggested():
    evidence_pack = EvidencePack(
        evidence_pack_id="pack-1",
        tenant_id="tenant-1",
    )

    assert evidence_pack.review_status == EvidenceReviewStatus.SUGGESTED
    assert evidence_pack.human_review_required is True
    assert evidence_pack.sensitivity == EvidenceSensitivity.RESTRICTED


def test_evidence_pack_is_passive_and_has_no_recommendation_field():
    evidence_pack = EvidencePack(
        evidence_pack_id="pack-1",
        tenant_id="tenant-1",
        evidence_artifacts=["artifact-1"],
        supporting_kpis=["kpi-result-1"],
        supporting_risks=["risk-result-1"],
        root_cause_category=RootCauseCategory.UNKNOWN,
    )

    assert evidence_pack.evidence_artifacts == ["artifact-1"]
    assert evidence_pack.supporting_kpis == ["kpi-result-1"]
    assert evidence_pack.supporting_risks == ["risk-result-1"]
    assert not hasattr(evidence_pack, "recommendation")


def test_models_do_not_expose_prohibited_content_or_decision_fields():
    models = [
        EvidenceArtifact,
        EvidenceLinkCandidate,
        EvidenceReview,
        EvidencePack,
    ]

    for model in models:
        model_fields = {field.name for field in fields(model)}
        assert model_fields.isdisjoint(PROHIBITED_MODEL_FIELDS)


def test_enum_values_match_board_approved_vocabulary():
    assert [item.value for item in EvidenceArtifactType] == [
        "QA_AUDIT",
        "RECORDING",
        "TRANSCRIPT_PLACEHOLDER",
        "TRANSCRIPT_IMPORTED",
        "REDACTED_TRANSCRIPT",
        "COACHING_EVIDENCE_PACK",
    ]
    assert [item.value for item in EvidenceSensitivity] == [
        "INTERNAL",
        "CONFIDENTIAL",
        "RESTRICTED",
    ]
    assert [item.value for item in EvidenceLifecycleStatus] == [
        "DISCOVERED",
        "REVIEW_PENDING",
        "APPROVED",
        "REJECTED",
        "ARCHIVED",
    ]
    assert [item.value for item in EvidenceReviewStatus] == [
        "SUGGESTED",
        "IN_REVIEW",
        "ACCEPTED",
        "REJECTED",
        "NEEDS_MORE_EVIDENCE",
    ]
    assert [item.value for item in EvidenceLinkStatus] == [
        "SUGGESTED",
        "REVIEW_PENDING",
        "APPROVED",
        "REJECTED",
        "ARCHIVED",
    ]
    assert [item.value for item in EvidenceLinkConfidence] == [
        "LOW",
        "MEDIUM",
        "HIGH",
    ]
    assert [item.value for item in EvidenceProcessingStatus] == [
        "METADATA_ONLY",
        "REVIEW_REQUIRED",
        "HUMAN_REVIEW_REQUIRED",
        "APPROVED_FOR_REFERENCE",
        "REJECTED_FOR_REFERENCE",
        "ARCHIVED",
    ]
    assert [item.value for item in RootCauseCategory] == [
        "SKILL",
        "KNOWLEDGE",
        "BEHAVIOR",
        "EXECUTION_DISCIPLINE",
        "ACCOUNTABILITY",
        "EXTERNAL_FACTOR",
        "UNKNOWN",
    ]
