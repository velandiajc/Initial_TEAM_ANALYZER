from dataclasses import dataclass

from app.domain.performance.rules.coaching_lineage_rules import (
    validate_governed_lineage,
)
from app.models.evidence import EvidencePack
from app.models.risk import RiskAssessmentResult


@dataclass(frozen=True)
class CoachingLineageSnapshot:
    lineage_id: str
    evidence_pack_id: str
    evidence_version_snapshot: str
    evidence_artifact_ids_snapshot: tuple[str, ...]
    risk_result_id: str
    risk_score_snapshot: float
    risk_level_snapshot: str
    risk_classification_snapshot: str
    risk_definition_version: str
    risk_rule_version: str


class CoachingLineageService:
    def validate_lineage(
        self,
        tenant_id: str,
        employee_id: str,
        evidence_pack: EvidencePack,
        risk_result: RiskAssessmentResult,
    ) -> str:
        return validate_governed_lineage(
            tenant_id,
            employee_id,
            evidence_pack,
            risk_result,
        )

    def build_snapshot(
        self,
        tenant_id: str,
        employee_id: str,
        evidence_pack: EvidencePack,
        risk_result: RiskAssessmentResult,
    ) -> CoachingLineageSnapshot:
        lineage_id = self.validate_lineage(
            tenant_id,
            employee_id,
            evidence_pack,
            risk_result,
        )
        return CoachingLineageSnapshot(
            lineage_id=lineage_id,
            evidence_pack_id=evidence_pack.evidence_pack_id,
            evidence_version_snapshot=evidence_pack.created_at.isoformat(),
            evidence_artifact_ids_snapshot=tuple(
                evidence_pack.evidence_artifacts
            ),
            risk_result_id=risk_result.result_id,
            risk_score_snapshot=risk_result.risk_score,
            risk_level_snapshot=risk_result.risk_level.value.upper(),
            risk_classification_snapshot=risk_result.risk_definition_id,
            risk_definition_version=risk_result.risk_definition_version,
            risk_rule_version=risk_result.rule_version_number,
        )
