from datetime import date, datetime

from app.application.workspace.dto import (
    EmployeeWorkspaceRequest,
    TeamWorkspaceRequest,
    WorkspaceRequest,
)
from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.domain.operational_impact import (
    OperationalImpactAssessment,
    OperationalImpactTimelineEvent,
    RiskPriorityAssessment,
)
from app.domain.operational_impact.value_objects import (
    ImpactLevel,
    PriorityLevel,
)
from app.domain.performance.entities import (
    CoachingCommitment,
    CoachingFollowUp,
    CoachingNote,
    CoachingSession,
    EmployeePerformanceTimelineEvent,
    PerformanceOpportunity,
)
from app.domain.performance.value_objects import (
    CoachingNoteVisibility,
    PerformanceTimelineEventSource,
)
from app.models.kpi_calculation import (
    KPICalculationResult,
    KPICalculationStatus,
)
from app.models.risk import (
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskLevel,
)


NOW = datetime(2026, 6, 12, 12, 0, 0)


class RecordingAuditService:
    def __init__(self):
        self.events = []

    def record(
        self,
        context,
        action,
        entity_type,
        entity_id,
        metadata=None,
    ):
        event = {
            "tenant_id": context.tenant_id,
            "requester_id": context.user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
        }
        self.events.append(event)
        return event


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


def workspace_request(tenant_id="tenant-1"):
    return WorkspaceRequest(
        tenant_id=tenant_id,
        requester_id="manager-1",
        supervisor_id="manager-1",
    )


def team_request(tenant_id="tenant-1", employee_ids=("employee-1",)):
    return TeamWorkspaceRequest(
        tenant_id=tenant_id,
        requester_id="manager-1",
        supervisor_id="manager-1",
        team_id="team-1",
        employee_ids=employee_ids,
    )


def employee_request(tenant_id="tenant-1"):
    return EmployeeWorkspaceRequest(
        tenant_id=tenant_id,
        requester_id="manager-1",
        supervisor_id="manager-1",
        employee_id="employee-1",
    )


def kpi_result(tenant_id="tenant-1", employee_id="employee-1"):
    return KPICalculationResult(
        tenant_id=tenant_id,
        result_id="kpi-result-1",
        kpi_id="qa-score",
        formula_version_id="formula-1",
        formula_version_number="1.0",
        period_start=datetime(2026, 5, 1),
        period_end=datetime(2026, 5, 31),
        scope={"employee_id": employee_id},
        value=72.0,
        status=KPICalculationStatus.SUCCESS,
        data_quality_status="trusted",
        source_reference="operational:qa",
        calculation_run_id="run-kpi-1",
        calculated_at=NOW,
        metadata={"lineage_id": ["kpi-lineage-1"]},
    )


def risk_result(tenant_id="tenant-1", employee_id="employee-1"):
    return RiskAssessmentResult(
        tenant_id=tenant_id,
        result_id="risk-result-1",
        risk_definition_id="performance-risk",
        rule_version_id="risk-rule-1",
        rule_version_number="1.0",
        entity_type="employee",
        entity_id=employee_id,
        period_start=datetime(2026, 5, 1),
        period_end=datetime(2026, 5, 31),
        risk_score=82.5,
        risk_level=RiskLevel.HIGH,
        status=RiskAssessmentStatus.SUCCESS,
        reason="Governed performance risk.",
        evidence={},
        source_reference="kpi:qa-score",
        assessment_run_id="run-risk-1",
        risk_definition_version="2.0",
        kpi_result_ids=["kpi-result-1"],
        formula_versions=[{
            "formula_version_id": "formula-1",
            "formula_version_number": "1.0",
        }],
        source_record_ids=["source-1"],
        source_validation_lineage={"status": ["valid"]},
        lineage_id="risk-lineage-1",
        assessed_at=NOW,
    )


def impact_assessment(
    tenant_id="tenant-1",
    employee_id="employee-1",
    score=68.0,
):
    return OperationalImpactAssessment(
        impact_assessment_id=f"impact-{employee_id}",
        tenant_id=tenant_id,
        impact_definition_id="operational-impact",
        entity_type="employee",
        entity_id=employee_id,
        assessment_period_start=datetime(2026, 5, 1),
        assessment_period_end=datetime(2026, 5, 31),
        impact_score=score,
        impact_level=ImpactLevel.HIGH,
        impact_definition_version="3.0",
        impact_factor_ids=("factor-qa",),
        impact_factor_versions={"factor-qa": "2.0"},
        threshold_versions={"factor-qa": "4.0"},
        weight_snapshots={"factor-qa": 1.0},
        factor_score_snapshots={"factor-qa": score},
        source_kpi_result_ids=("kpi-result-1",),
        source_risk_result_ids=("risk-result-1",),
        lineage_id=f"impact-lineage-{employee_id}",
        created_by="owner-1",
        created_at=NOW,
    )


def priority_assessment(
    tenant_id="tenant-1",
    employee_id="employee-1",
    score=88.0,
    level=PriorityLevel.IMMEDIATE_INTERVENTION,
    reason="Immediate governed intervention required.",
):
    return RiskPriorityAssessment(
        priority_assessment_id=f"priority-{employee_id}-{score}",
        tenant_id=tenant_id,
        risk_result_id="risk-result-1",
        risk_definition_version="2.0",
        risk_rule_version="1.0",
        impact_assessment_id=f"impact-{employee_id}",
        impact_definition_version="3.0",
        entity_type="employee",
        entity_id=employee_id,
        risk_score_snapshot=82.5,
        impact_score_snapshot=68.0,
        priority_score=score,
        priority_level=level,
        priority_reason=reason,
        lineage_id=f"priority-lineage-{employee_id}-{score}",
        created_by="manager-1",
        created_at=NOW,
    )


def opportunity(tenant_id="tenant-1"):
    return PerformanceOpportunity(
        opportunity_id="opportunity-1",
        tenant_id=tenant_id,
        employee_id="employee-1",
        opportunity_type="QA",
        business_reason="Governed performance opportunity.",
        evidence_pack_id="evidence-pack-1",
        risk_result_id="risk-result-1",
        owner="manager-1",
        lineage_id="opportunity-lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
        created_at=NOW,
        updated_at=NOW,
    )


def session(tenant_id="tenant-1"):
    return CoachingSession(
        coaching_session_id="session-1",
        tenant_id=tenant_id,
        employee_id="employee-1",
        session_owner_id="manager-1",
        performance_opportunity_id="opportunity-1",
        evidence_pack_id="evidence-pack-1",
        evidence_version_snapshot="1.0",
        evidence_artifact_ids_snapshot=("artifact-1",),
        risk_result_id="risk-result-1",
        risk_score_snapshot=82.5,
        risk_level_snapshot="HIGH",
        risk_classification_snapshot="performance-risk",
        risk_definition_version="2.0",
        risk_rule_version="1.0",
        coaching_version="1.0",
        lineage_id="coaching-lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
        created_at=NOW,
        updated_at=NOW,
    )


def commitment(tenant_id="tenant-1"):
    return CoachingCommitment(
        commitment_id="commitment-1",
        tenant_id=tenant_id,
        session_id="session-1",
        employee_id="employee-1",
        description="Use the approved QA procedure.",
        target_date=date(2026, 6, 1),
        lineage_id="commitment-lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
        created_at=NOW,
        updated_at=NOW,
    )


def followup(tenant_id="tenant-1"):
    return CoachingFollowUp(
        followup_id="followup-1",
        tenant_id=tenant_id,
        session_id="session-1",
        commitment_id="commitment-1",
        reviewer_id="manager-1",
        outcome="",
        lineage_id="followup-lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
        created_at=NOW,
        updated_at=NOW,
    )


def note(visibility, note_id, tenant_id="tenant-1"):
    return CoachingNote(
        note_id=note_id,
        tenant_id=tenant_id,
        session_id="session-1",
        visibility_level=visibility,
        content_reference=f"notes/{note_id}",
        lineage_id=f"{note_id}-lineage",
        created_by="manager-1",
        updated_by="manager-1",
        created_at=NOW,
        updated_at=NOW,
    )


def performance_event(tenant_id="tenant-1"):
    return EmployeePerformanceTimelineEvent(
        timeline_event_id="performance-event-1",
        tenant_id=tenant_id,
        employee_id="employee-1",
        event_type="COACHING_SESSION_CREATED",
        event_source=PerformanceTimelineEventSource.COACHING,
        source_entity_id="session-1",
        lineage_id="performance-event-lineage-1",
        created_by="manager-1",
        updated_by="manager-1",
        created_at=NOW,
        updated_at=NOW,
    )


def impact_event(tenant_id="tenant-1"):
    return OperationalImpactTimelineEvent(
        timeline_event_id="impact-event-1",
        tenant_id=tenant_id,
        employee_id="employee-1",
        impact_assessment_id="impact-employee-1",
        priority_assessment_id="priority-employee-1-88.0",
        event_type="OPERATIONAL_IMPACT_CHANGED",
        material_change_reason="Governed material change.",
        impact_level_snapshot=ImpactLevel.HIGH,
        priority_level_snapshot=PriorityLevel.IMMEDIATE_INTERVENTION,
        created_by="manager-1",
        created_at=NOW,
    )


def notes(tenant_id="tenant-1"):
    return (
        note(CoachingNoteVisibility.SHARED, "shared-note", tenant_id),
        note(
            CoachingNoteVisibility.MANAGER_ONLY,
            "manager-note",
            tenant_id,
        ),
        note(
            CoachingNoteVisibility.LEADERSHIP_ONLY,
            "leadership-note",
            tenant_id,
        ),
    )
