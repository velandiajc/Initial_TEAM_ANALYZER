import pytest

from app.models.kpi import (
    FormulaStatus,
    FormulaVersion,
    KPIDefinition,
    KPIDomain,
    KPILifecycle,
    KPIThreshold,
)


def test_kpi_definition_requires_owner_and_steward():
    with pytest.raises(ValueError, match="owner_user_id is required"):
        KPIDefinition(
            kpi_id="csat",
            tenant_id="tenant-1",
            name="CSAT",
            domain=KPIDomain.CUSTOMER_EXPERIENCE,
            owner_user_id="",
            steward_user_id="steward-1",
        )

    with pytest.raises(ValueError, match="steward_user_id is required"):
        KPIDefinition(
            kpi_id="csat",
            tenant_id="tenant-1",
            name="CSAT",
            domain=KPIDomain.CUSTOMER_EXPERIENCE,
            owner_user_id="owner-1",
            steward_user_id="",
        )


def test_kpi_definition_normalizes_domain_and_lifecycle_values():
    definition = KPIDefinition(
        kpi_id="qa-score",
        tenant_id="tenant-1",
        name="QA Score",
        domain="quality",
        lifecycle="pending approval",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
    )

    assert definition.domain == KPIDomain.QUALITY
    assert definition.lifecycle == KPILifecycle.PENDING_APPROVAL


def test_threshold_requires_at_least_one_governed_value():
    with pytest.raises(ValueError, match="at least one governed threshold value"):
        KPIThreshold(
            threshold_id="threshold-1",
            tenant_id="tenant-1",
            kpi_id="csat",
            name="Critical",
            risk_level="critical",
        )


def test_formula_creator_cannot_approve_own_formula():
    formula = FormulaVersion(
        formula_version_id="formula-1",
        tenant_id="tenant-1",
        kpi_id="csat",
        version="1.0",
        expression="survey_score_average",
        created_by="owner-1",
    )

    with pytest.raises(PermissionError, match="Creator cannot approve own formula"):
        formula.approve("owner-1")


def test_formula_approval_records_approver_and_status():
    formula = FormulaVersion(
        formula_version_id="formula-1",
        tenant_id="tenant-1",
        kpi_id="csat",
        version="1.0",
        expression="survey_score_average",
        created_by="owner-1",
    )

    formula.approve("approver-1")

    assert formula.status == FormulaStatus.APPROVED
    assert formula.approved_by == "approver-1"
    assert formula.approved_at is not None
