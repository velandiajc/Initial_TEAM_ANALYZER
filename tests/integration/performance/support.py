from datetime import datetime

from app.application.performance.services import (
    CoachingCommitmentService,
    CoachingFollowUpService,
    CoachingNoteService,
    CoachingSessionService,
    EmployeePerformanceTimelineService,
    PerformanceOpportunityService,
)
from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.infrastructure.persistence.performance import (
    SQLiteCoachingCommitmentRepository,
    SQLiteCoachingFollowUpRepository,
    SQLiteCoachingNoteRepository,
    SQLiteCoachingSessionRepository,
    SQLiteEmployeePerformanceTimelineRepository,
    SQLitePerformanceOpportunityRepository,
)
from app.models.evidence import EvidencePack, EvidenceReviewStatus
from app.models.risk import (
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskLevel,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository


def context(
    role=GovernanceRole.PERFORMANCE_MANAGER,
    tenant_id="tenant-1",
    user_id="manager-1",
):
    role_value = getattr(role, "value", role)
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles={role_value} if role_value else set(),
    )


def risk_result(tenant_id="tenant-1"):
    return RiskAssessmentResult(
        tenant_id=tenant_id,
        risk_definition_id="csat-risk",
        rule_version_id="risk-rule-1",
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
        assessment_run_id="risk-run-1",
        risk_definition_version="2.0",
        kpi_result_ids=["kpi-result-1"],
        formula_versions=[{"formula_version_id": "formula-1"}],
        source_record_ids=["source-1"],
        source_validation_lineage={"status": ["valid"]},
        lineage_id="lineage-1",
        result_id="risk-result-1",
    )


def evidence_pack(tenant_id="tenant-1"):
    return EvidencePack(
        evidence_pack_id="pack-1",
        tenant_id=tenant_id,
        agent_id="agent-1",
        review_status=EvidenceReviewStatus.ACCEPTED,
        evidence_artifacts=["artifact-1"],
        supporting_kpis=["kpi-result-1"],
        supporting_risks=["risk-result-1"],
    )


def build_stack(tmp_path):
    database = DatabaseService(tmp_path / "performance.db")
    database.initialize()
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)
    repositories = {
        "opportunities": SQLitePerformanceOpportunityRepository(database),
        "sessions": SQLiteCoachingSessionRepository(database),
        "commitments": SQLiteCoachingCommitmentRepository(database),
        "followups": SQLiteCoachingFollowUpRepository(database),
        "notes": SQLiteCoachingNoteRepository(database),
        "timeline": SQLiteEmployeePerformanceTimelineRepository(database),
    }
    timeline_service = EmployeePerformanceTimelineService(
        repositories["timeline"],
        audit_service,
    )
    services = {
        "opportunities": PerformanceOpportunityService(
            repositories["opportunities"],
            audit_service,
        ),
        "sessions": CoachingSessionService(
            repositories["sessions"],
            repositories["opportunities"],
            timeline_service,
            audit_service,
        ),
        "commitments": CoachingCommitmentService(
            repositories["commitments"],
            repositories["sessions"],
            timeline_service,
            audit_service,
        ),
        "followups": CoachingFollowUpService(
            repositories["followups"],
            repositories["commitments"],
            repositories["sessions"],
            timeline_service,
            audit_service,
        ),
        "notes": CoachingNoteService(
            repositories["notes"],
            repositories["sessions"],
            audit_service,
        ),
        "timeline": timeline_service,
    }
    return {
        "database": database,
        "audit_repository": audit_repository,
        "audit_service": audit_service,
        "repositories": repositories,
        "services": services,
    }


def create_session_foundation(stack, ctx=None):
    ctx = ctx or context()
    risk = risk_result(ctx.tenant_id)
    pack = evidence_pack(ctx.tenant_id)
    opportunity = stack["services"]["opportunities"].create_opportunity(
        ctx,
        "agent-1",
        "CSAT",
        "Governed CSAT performance opportunity.",
        pack,
        risk,
        opportunity_id="opportunity-1",
    )
    opportunity = stack["services"]["opportunities"].accept_opportunity(
        ctx,
        opportunity.opportunity_id,
    )
    session = stack["services"]["sessions"].create_session(
        ctx,
        "agent-1",
        ctx.user_id,
        opportunity.opportunity_id,
        pack,
        risk,
        "1.0",
        session_id="session-1",
    )
    return risk, pack, opportunity, session
