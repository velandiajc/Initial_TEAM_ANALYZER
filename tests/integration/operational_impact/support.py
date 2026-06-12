from datetime import date, datetime

from app.application.operational_impact.services import (
    OperationalImpactAssessmentService,
    OperationalImpactDefinitionService,
    OperationalImpactFactorService,
    OperationalImpactTimelineService,
    RiskPriorityService,
)
from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.domain.operational_impact import OperationalImpactAssessmentRequest
from app.infrastructure.persistence.operational_impact import (
    SQLiteOperationalImpactAssessmentRepository,
    SQLiteOperationalImpactDefinitionRepository,
    SQLiteOperationalImpactFactorRepository,
    SQLiteOperationalImpactTimelineRepository,
    SQLiteRiskPriorityAssessmentRepository,
)
from app.models.kpi import (
    FormulaStatus,
    FormulaVersion,
    KPIDefinition,
    KPIDomain,
)
from app.models.kpi_calculation import (
    KPICalculationResult,
    KPICalculationStatus,
)
from app.models.risk import (
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskDefinition,
    RiskDefinitionLifecycle,
    RiskLevel,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_kpi_calculation_result_repository import (
    SQLiteKPICalculationResultRepository,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)
from app.services.sqlite_risk_repository import SQLiteRiskDefinitionRepository


FACTOR_KPIS = (
    ("survey-volume", "Survey Volume"),
    ("handled-contacts", "Handled Contacts"),
    ("qa-critical-errors", "QA Critical Errors"),
    ("attendance-instability", "Attendance Instability"),
    ("adherence-deviation", "Adherence Deviation"),
)
PERIOD_START = datetime(2026, 5, 1)
PERIOD_END = datetime(2026, 5, 31)


def context(
    role=GovernanceRole.KPI_OWNER,
    tenant_id="tenant-1",
    user_id="owner-1",
):
    role_value = getattr(role, "value", role)
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles={role_value} if role_value else set(),
    )


def build_stack(tmp_path):
    database = DatabaseService(tmp_path / "operational-impact.db")
    database.initialize()
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)
    kpi_definition_repository = SQLiteKPIDefinitionRepository(database)
    kpi_result_repository = SQLiteKPICalculationResultRepository(
        database,
        kpi_definition_repository,
    )
    risk_repository = SQLiteRiskDefinitionRepository(database)
    repositories = {
        "definitions": SQLiteOperationalImpactDefinitionRepository(database),
        "factors": SQLiteOperationalImpactFactorRepository(database),
        "assessments": SQLiteOperationalImpactAssessmentRepository(database),
        "priorities": SQLiteRiskPriorityAssessmentRepository(database),
        "timeline": SQLiteOperationalImpactTimelineRepository(database),
    }
    timeline_service = OperationalImpactTimelineService(
        repositories["timeline"],
        audit_service,
    )
    services = {
        "definitions": OperationalImpactDefinitionService(
            repositories["definitions"],
            audit_service,
        ),
        "factors": OperationalImpactFactorService(
            repositories["factors"],
            repositories["definitions"],
            audit_service,
        ),
        "assessments": OperationalImpactAssessmentService(
            repositories["definitions"],
            repositories["factors"],
            repositories["assessments"],
            kpi_result_repository,
            risk_repository,
            audit_service,
        ),
        "priorities": RiskPriorityService(
            repositories["priorities"],
            repositories["assessments"],
            risk_repository,
            audit_service,
            timeline_service,
        ),
        "timeline": timeline_service,
    }
    return {
        "database": database,
        "audit_repository": audit_repository,
        "audit_service": audit_service,
        "kpi_definition_repository": kpi_definition_repository,
        "kpi_result_repository": kpi_result_repository,
        "risk_repository": risk_repository,
        "repositories": repositories,
        "services": services,
    }


def register_governed_inputs(stack, tenant_id="tenant-1"):
    owner = context(tenant_id=tenant_id)
    for kpi_id, name in FACTOR_KPIS:
        stack["kpi_definition_repository"].upsert_definition(
            owner,
            KPIDefinition(
                kpi_id=kpi_id,
                tenant_id=tenant_id,
                name=name,
                domain=KPIDomain.OPERATIONS,
                owner_user_id=owner.user_id,
                steward_user_id="steward-1",
                created_by=owner.user_id,
            ),
        )
        stack["kpi_definition_repository"].upsert_formula_version(
            owner,
            FormulaVersion(
                formula_version_id=f"{kpi_id}-formula-1",
                tenant_id=tenant_id,
                kpi_id=kpi_id,
                version="1.0",
                expression="count_records",
                created_by=owner.user_id,
                status=FormulaStatus.APPROVED,
                approved_by="approver-1",
                approved_at=datetime(2026, 1, 1),
            ),
        )
    stack["risk_repository"].upsert_definition(
        owner,
        RiskDefinition(
            risk_definition_id="performance-risk",
            tenant_id=tenant_id,
            name="Performance Risk",
            category="performance",
            owner_user_id=owner.user_id,
            steward_user_id="steward-1",
            lifecycle=RiskDefinitionLifecycle.ACTIVE,
            created_by=owner.user_id,
            metadata={"version": "1.0"},
        ),
    )


def create_kpi_results(stack, prefix, value, tenant_id="tenant-1"):
    owner = context(tenant_id=tenant_id)
    results = []
    for kpi_id, _ in FACTOR_KPIS:
        result = KPICalculationResult(
            tenant_id=tenant_id,
            result_id=f"{prefix}-{kpi_id}",
            kpi_id=kpi_id,
            formula_version_id=f"{kpi_id}-formula-1",
            formula_version_number="1.0",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            scope={"employee_id": "employee-1"},
            value=value,
            status=KPICalculationStatus.SUCCESS,
            data_quality_status="trusted",
            source_reference=f"operational:{prefix}",
            calculation_run_id=f"run-{prefix}-{kpi_id}",
            metadata={
                "source_record_ids": [f"source-{prefix}-{kpi_id}"],
                "source_references": [f"operational:{prefix}"],
                "source_types": ["operational"],
                "source_version": ["1.0"],
                "lineage_id": [f"lineage-{prefix}-{kpi_id}"],
            },
        )
        stack["kpi_result_repository"].save(owner, result)
        results.append(result)
    return results


def create_risk_result(
    stack,
    result_id="risk-result-1",
    risk_score=100,
    tenant_id="tenant-1",
):
    owner = context(tenant_id=tenant_id)
    result = RiskAssessmentResult(
        tenant_id=tenant_id,
        result_id=result_id,
        risk_definition_id="performance-risk",
        rule_version_id="risk-rule-1",
        rule_version_number="1.0",
        entity_type="employee",
        entity_id="employee-1",
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        risk_score=risk_score,
        risk_level=RiskLevel.CRITICAL,
        status=RiskAssessmentStatus.SUCCESS,
        reason="Governed performance risk.",
        evidence={},
        source_reference="kpi:survey-volume",
        assessment_run_id=f"run-{result_id}",
        risk_definition_version="1.0",
        kpi_result_ids=["baseline-survey-volume"],
        formula_versions=[{
            "kpi_id": "survey-volume",
            "formula_version_id": "survey-volume-formula-1",
            "formula_version_number": "1.0",
        }],
        source_record_ids=["source-risk-1"],
        source_validation_lineage={"status": ["valid"]},
        lineage_id=f"lineage-{result_id}",
    )
    stack["risk_repository"].save_result(owner, result)
    return result


def create_active_framework(stack):
    owner = context()
    approver = context(
        GovernanceRole.KPI_APPROVER,
        user_id="approver-1",
    )
    definition = stack["services"]["definitions"].create_definition(
        owner,
        "operational-impact",
        "Operational Impact",
        "Governed operational consequence assessment.",
        "performance",
        "owner-1",
        "steward-1",
        "1.0",
        date(2026, 6, 1),
    )
    stack["services"]["definitions"].approve_definition(
        approver,
        definition.impact_definition_id,
        definition.impact_definition_version,
    )
    definition = stack["services"]["definitions"].activate_definition(
        approver,
        definition.impact_definition_id,
        definition.impact_definition_version,
    )
    for kpi_id, name in FACTOR_KPIS:
        factor = stack["services"]["factors"].create_factor(
            owner,
            f"factor-{kpi_id}",
            definition.impact_definition_id,
            definition.impact_definition_version,
            name,
            f"Governed {name.lower()} impact factor.",
            f"kpi:{kpi_id}",
            0.2,
            "HIGHER_IS_WORSE",
            "1.0",
            0,
            100,
            "1.0",
            "owner-1",
            "steward-1",
            date(2026, 6, 1),
        )
        stack["services"]["factors"].approve_factor(
            approver,
            factor.impact_factor_id,
            factor.impact_factor_version,
        )
        stack["services"]["factors"].activate_factor(
            approver,
            factor.impact_factor_id,
            factor.impact_factor_version,
        )
    return definition


def impact_request(results):
    return OperationalImpactAssessmentRequest(
        impact_definition_id="operational-impact",
        entity_type="employee",
        entity_id="employee-1",
        assessment_period_start=PERIOD_START,
        assessment_period_end=PERIOD_END,
        source_kpi_result_ids=tuple(result.result_id for result in results),
    )


def prepare_stack(tmp_path):
    stack = build_stack(tmp_path)
    register_governed_inputs(stack)
    baseline = create_kpi_results(stack, "baseline", 10)
    risk = create_risk_result(stack)
    create_active_framework(stack)
    return stack, baseline, risk
