from app.models.evidence import EvidencePack, EvidenceReviewStatus
from app.models.risk import RiskAssessmentResult


def require_lineage_id(lineage_id: str) -> str:
    return require_text(lineage_id, "lineage_id")


def validate_governed_lineage(
    tenant_id: str,
    employee_id: str,
    evidence_pack: EvidencePack,
    risk_result: RiskAssessmentResult,
) -> str:
    require_text(tenant_id, "tenant_id")
    require_text(employee_id, "employee_id")

    if evidence_pack.tenant_id != tenant_id:
        raise PermissionError("Evidence pack tenant does not match context.")

    if risk_result.tenant_id != tenant_id:
        raise PermissionError("Risk result tenant does not match context.")

    if evidence_pack.agent_id and evidence_pack.agent_id != employee_id:
        raise ValueError("Evidence pack employee does not match coaching employee.")

    if evidence_pack.review_status != EvidenceReviewStatus.ACCEPTED:
        raise ValueError("Evidence pack must be accepted before coaching use.")

    if risk_result.result_id not in evidence_pack.supporting_risks:
        raise ValueError("Evidence pack must reference the governed risk result.")

    missing_kpis = set(risk_result.kpi_result_ids) - set(
        evidence_pack.supporting_kpis
    )
    if missing_kpis:
        raise ValueError("Evidence pack is missing governed KPI result lineage.")

    return require_lineage_id(risk_result.lineage_id)


def require_text(value, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized
