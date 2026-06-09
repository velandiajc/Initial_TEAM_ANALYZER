from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.risk import (
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskDefinition,
    RiskDefinitionLifecycle,
    RiskLevel,
    RiskRuleStatus,
    RiskRuleVersion,
)
from app.services.database_service import DatabaseService
from app.services.sqlite_risk_repository import SQLiteRiskDefinitionRepository


def context(tenant_id="tenant-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )


def repository(tmp_path):
    database = DatabaseService(tmp_path / "risk.db")
    database.initialize()
    return SQLiteRiskDefinitionRepository(database)


def definition(tenant_id="tenant-1"):
    return RiskDefinition(
        risk_definition_id="csat-critical-risk",
        tenant_id=tenant_id,
        name="CSAT Critical Risk",
        category="customer_experience",
        owner_user_id="owner-1",
        steward_user_id="steward-1",
        created_by="owner-1",
    )


def approved_rule():
    return RiskRuleVersion(
        rule_version_id="rule-1",
        tenant_id="tenant-1",
        risk_definition_id="csat-critical-risk",
        version="1.0",
        handler_key="threshold",
        parameters={
            "metric_name": "avg_csat",
            "operator": "lt",
            "threshold": 80,
            "risk_level": "critical",
        },
        created_by="owner-1",
        status=RiskRuleStatus.ACTIVE,
        approved_by="approver-1",
        approved_at=datetime(2026, 1, 1),
        effective_from=datetime(2026, 1, 1),
        effective_to=datetime(2026, 12, 31),
        is_active=True,
    )


def test_risk_definition_repository_is_tenant_scoped(tmp_path):
    repo = repository(tmp_path)
    repo.upsert_definition(context(), definition())

    assert repo.get_definition(context("tenant-1"), "csat-critical-risk")
    assert repo.get_definition(context("tenant-2"), "csat-critical-risk") is None
    assert repo.list_definitions(context("tenant-2")) == []


def test_risk_definition_repository_rejects_cross_tenant_write(tmp_path):
    repo = repository(tmp_path)

    with pytest.raises(PermissionError, match="tenant-scoped"):
        repo.upsert_definition(context("tenant-1"), definition("tenant-2"))


def test_rule_lineage_and_approved_active_resolution_are_persisted(tmp_path):
    repo = repository(tmp_path)
    repo.upsert_definition(context(), definition())
    rule = approved_rule()
    repo.upsert_rule_version(context(), rule)

    lineage = repo.get_rule_lineage(context(), "csat-critical-risk")
    active_rules = repo.get_approved_active_rules_for_period(
        context(),
        "csat-critical-risk",
        datetime(2026, 3, 1),
        datetime(2026, 3, 31),
    )

    assert [item.version for item in lineage] == ["1.0"]
    assert active_rules[0].rule_version_id == "rule-1"


def test_repository_rejects_approved_risk_rule_mutation(tmp_path):
    repo = repository(tmp_path)
    repo.upsert_definition(context(), definition())
    repo.upsert_rule_version(context(), approved_rule())
    mutated = approved_rule()
    object.__setattr__(mutated, "handler_key", "different_handler")

    with pytest.raises(PermissionError, match="immutable"):
        repo.upsert_rule_version(context(), mutated)


def test_risk_result_repository_is_tenant_scoped(tmp_path):
    repo = repository(tmp_path)
    repo.upsert_definition(context(), definition())
    result = RiskAssessmentResult(
        tenant_id="tenant-1",
        risk_definition_id="csat-critical-risk",
        rule_version_id="rule-1",
        rule_version_number="1.0",
        entity_type="agent",
        entity_id="agent-1",
        period_start=datetime(2026, 3, 1),
        period_end=datetime(2026, 3, 31),
        risk_score=100.0,
        risk_level=RiskLevel.CRITICAL,
        status=RiskAssessmentStatus.SUCCESS,
        reason="Average CSAT below governed threshold.",
        evidence={
            "metric_name": "avg_csat",
            "actual_value": 72,
        },
        source_reference="survey:unit-test",
        assessment_run_id="run-1",
        risk_definition_version="1.0",
        kpi_result_ids=["kpi-result-1"],
        formula_versions=[{
            "kpi_id": "csat",
            "formula_version_id": "formula-1",
            "formula_version_number": "1.0",
        }],
        source_record_ids=["source-1"],
        source_validation_lineage={
            "source_validation_status": ["valid"],
            "data_quality_status": ["valid"],
        },
        lineage_id="lineage-1",
    )

    repo.save_result(context(), result)
    persisted = repo.get_result(context("tenant-1"), result.result_id)

    assert persisted is not None
    assert persisted.risk_score == 100.0
    assert persisted.kpi_result_ids == ["kpi-result-1"]
    assert persisted.formula_versions[0]["formula_version_id"] == "formula-1"
    assert persisted.source_record_ids == ["source-1"]
    assert persisted.source_validation_lineage["source_validation_status"] == ["valid"]
    assert persisted.lineage_id == "lineage-1"
    assert repo.get_result(context("tenant-2"), result.result_id) is None
    assert repo.list_results_for_definition(
        context("tenant-2"),
        "csat-critical-risk"
    ) == []


def test_lifecycle_updates_are_persisted(tmp_path):
    repo = repository(tmp_path)
    repo.upsert_definition(context(), definition())

    updated = repo.update_lifecycle(
        context(),
        "csat-critical-risk",
        RiskDefinitionLifecycle.ACTIVE,
    )

    assert updated.lifecycle == RiskDefinitionLifecycle.ACTIVE


def test_risk_result_repository_rejects_missing_required_lineage(tmp_path):
    repo = repository(tmp_path)
    repo.upsert_definition(context(), definition())

    with pytest.raises(ValueError, match="KPI result lineage"):
        RiskAssessmentResult(
            tenant_id="tenant-1",
            risk_definition_id="csat-critical-risk",
            rule_version_id="rule-1",
            rule_version_number="1.0",
            entity_type="agent",
            entity_id="agent-1",
            period_start=datetime(2026, 3, 1),
            period_end=datetime(2026, 3, 31),
            risk_score=100.0,
            risk_level=RiskLevel.CRITICAL,
            status=RiskAssessmentStatus.SUCCESS,
            reason="Average CSAT below governed threshold.",
            evidence={},
            source_reference="survey:unit-test",
            assessment_run_id="run-1",
            risk_definition_version="1.0",
            kpi_result_ids=[],
            formula_versions=[{
                "kpi_id": "csat",
                "formula_version_id": "formula-1",
                "formula_version_number": "1.0",
            }],
            source_record_ids=[],
            source_validation_lineage={},
            lineage_id="lineage-1",
        )
