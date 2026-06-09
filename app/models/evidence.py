from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.models.kpi import utc_now


class EvidenceArtifactType(Enum):
    QA_AUDIT = "QA_AUDIT"
    RECORDING = "RECORDING"
    TRANSCRIPT_PLACEHOLDER = "TRANSCRIPT_PLACEHOLDER"
    TRANSCRIPT_IMPORTED = "TRANSCRIPT_IMPORTED"
    REDACTED_TRANSCRIPT = "REDACTED_TRANSCRIPT"
    COACHING_EVIDENCE_PACK = "COACHING_EVIDENCE_PACK"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceArtifactType | str"
    ) -> "EvidenceArtifactType":
        return _enum_from_value(cls, value, "evidence artifact type")


class EvidenceSensitivity(Enum):
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceSensitivity | str"
    ) -> "EvidenceSensitivity":
        return _enum_from_value(cls, value, "evidence sensitivity")


class EvidenceLifecycleStatus(Enum):
    DISCOVERED = "DISCOVERED"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceLifecycleStatus | str"
    ) -> "EvidenceLifecycleStatus":
        return _enum_from_value(cls, value, "evidence lifecycle status")


class EvidenceReviewStatus(Enum):
    SUGGESTED = "SUGGESTED"
    IN_REVIEW = "IN_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceReviewStatus | str"
    ) -> "EvidenceReviewStatus":
        return _enum_from_value(cls, value, "evidence review status")


class EvidenceLinkStatus(Enum):
    SUGGESTED = "SUGGESTED"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceLinkStatus | str"
    ) -> "EvidenceLinkStatus":
        return _enum_from_value(cls, value, "evidence link status")


class EvidenceLinkConfidence(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceLinkConfidence | str"
    ) -> "EvidenceLinkConfidence":
        return _enum_from_value(cls, value, "evidence link confidence")


class EvidenceProcessingStatus(Enum):
    METADATA_ONLY = "METADATA_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    APPROVED_FOR_REFERENCE = "APPROVED_FOR_REFERENCE"
    REJECTED_FOR_REFERENCE = "REJECTED_FOR_REFERENCE"
    ARCHIVED = "ARCHIVED"

    @classmethod
    def from_value(
        cls,
        value: "EvidenceProcessingStatus | str"
    ) -> "EvidenceProcessingStatus":
        return _enum_from_value(cls, value, "evidence processing status")


class RootCauseCategory(Enum):
    SKILL = "SKILL"
    KNOWLEDGE = "KNOWLEDGE"
    BEHAVIOR = "BEHAVIOR"
    EXECUTION_DISCIPLINE = "EXECUTION_DISCIPLINE"
    ACCOUNTABILITY = "ACCOUNTABILITY"
    EXTERNAL_FACTOR = "EXTERNAL_FACTOR"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_value(
        cls,
        value: "RootCauseCategory | str"
    ) -> "RootCauseCategory":
        return _enum_from_value(cls, value, "root cause category")


@dataclass
class EvidenceArtifact:
    artifact_id: str
    tenant_id: str
    artifact_type: EvidenceArtifactType
    source_reference: str
    linked_record_id: str | None = None
    discovered_at: datetime = field(default_factory=utc_now)
    status: EvidenceLifecycleStatus = EvidenceLifecycleStatus.DISCOVERED
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    lineage_id: str | None = None
    sensitivity: EvidenceSensitivity = EvidenceSensitivity.RESTRICTED
    processing_status: EvidenceProcessingStatus = (
        EvidenceProcessingStatus.METADATA_ONLY
    )
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.source_reference, "source_reference")
        self.artifact_type = EvidenceArtifactType.from_value(self.artifact_type)
        self.status = EvidenceLifecycleStatus.from_value(self.status)
        self.sensitivity = EvidenceSensitivity.from_value(self.sensitivity)
        self.processing_status = EvidenceProcessingStatus.from_value(
            self.processing_status
        )
        self.metadata = _string_metadata(self.metadata)


@dataclass
class EvidenceLinkCandidate:
    candidate_id: str
    tenant_id: str
    source_record_id: str
    evidence_reference: str
    confidence_level: EvidenceLinkConfidence
    confidence_score: float | None = None
    status: EvidenceLinkStatus = EvidenceLinkStatus.SUGGESTED
    created_at: datetime = field(default_factory=utc_now)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    match_reason: str | None = None
    lineage_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.source_record_id, "source_record_id")
        _require_text(self.evidence_reference, "evidence_reference")
        self.confidence_level = EvidenceLinkConfidence.from_value(
            self.confidence_level
        )
        self.status = EvidenceLinkStatus.from_value(self.status)
        if self.confidence_score is not None:
            self.confidence_score = float(self.confidence_score)
            if self.confidence_score < 0 or self.confidence_score > 1:
                raise ValueError("confidence_score must be between 0 and 1.")


@dataclass
class EvidenceReview:
    review_id: str
    tenant_id: str
    candidate_id: str | None = None
    artifact_id: str | None = None
    review_status: EvidenceReviewStatus = EvidenceReviewStatus.SUGGESTED
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    lineage_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.review_id, "review_id")
        _require_text(self.tenant_id, "tenant_id")
        self.review_status = EvidenceReviewStatus.from_value(self.review_status)


@dataclass
class EvidencePack:
    evidence_pack_id: str
    tenant_id: str
    agent_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    review_status: EvidenceReviewStatus = EvidenceReviewStatus.SUGGESTED
    evidence_artifacts: list[str] = field(default_factory=list)
    supporting_kpis: list[str] = field(default_factory=list)
    supporting_risks: list[str] = field(default_factory=list)
    notes: str | None = None
    sensitivity: EvidenceSensitivity = EvidenceSensitivity.RESTRICTED
    human_review_required: bool = True
    root_cause_category: RootCauseCategory = RootCauseCategory.UNKNOWN

    def __post_init__(self) -> None:
        _require_text(self.evidence_pack_id, "evidence_pack_id")
        _require_text(self.tenant_id, "tenant_id")
        self.review_status = EvidenceReviewStatus.from_value(self.review_status)
        self.sensitivity = EvidenceSensitivity.from_value(self.sensitivity)
        self.root_cause_category = RootCauseCategory.from_value(
            self.root_cause_category
        )
        self.evidence_artifacts = _normalized_text_list(self.evidence_artifacts)
        self.supporting_kpis = _normalized_text_list(self.supporting_kpis)
        self.supporting_risks = _normalized_text_list(self.supporting_risks)
        if self.human_review_required is not True:
            raise ValueError("EvidencePack requires human_review_required to be True.")


def _enum_from_value(enum_cls: type[Enum], value: Any, label: str) -> Enum:
    if isinstance(value, enum_cls):
        return value

    normalized = str(value).strip().upper().replace(" ", "_").replace("-", "_")
    for enum_value in enum_cls:
        if enum_value.value == normalized or enum_value.name == normalized:
            return enum_value

    raise ValueError(f"Unsupported {label}: {value}")


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")


def _normalized_text_list(values: list[str]) -> list[str]:
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]


def _string_metadata(metadata: dict[str, str]) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in metadata.items()
    }
