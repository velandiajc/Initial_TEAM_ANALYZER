from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
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
from app.services.database_service import DatabaseService
from app.services.sqlite_kpi_calculation_result_repository import (
    SQLiteKPICalculationResultRepository,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)


def context(role=GovernanceRole.KPI_OWNER, tenant_id="tenant-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="owner-1",
        roles={role.value},
    )


def create_repo(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    definition_repository = SQLiteKPIDefinitionRepository(database)
    definition_repository.upsert_definition(
        context(),
        KPIDefinition(
            kpi_id="csat",
            tenant_id="tenant-1",
            name="CSAT",
            domain=KPIDomain.CUSTOMER_EXPERIENCE,
            owner_user_id="owner-1",
            steward_user_id="steward-1",
            created_by="owner-1",
        )
    )
    definition_repository.upsert_formula_version(
        context(),
        FormulaVersion(
            formula_version_id="formula-1",
            tenant_id="tenant-1",
            kpi_id="csat",
            version="1.0",
            expression="count_records",
            created_by="owner-1",
            status=FormulaStatus.APPROVED,
            approved_by="approver-1",
            approved_at=datetime(2026, 1, 1),
        )
    )
    definition_repository.upsert_definition(
        context(),
        KPIDefinition(
            kpi_id="qa",
            tenant_id="tenant-1",
            name="QA",
            domain=KPIDomain.QUALITY,
            owner_user_id="owner-1",
            steward_user_id="steward-1",
            created_by="owner-1",
        )
    )
    definition_repository.upsert_formula_version(
        context(),
        FormulaVersion(
            formula_version_id="qa-formula",
            tenant_id="tenant-1",
            kpi_id="qa",
            version="1.0",
            expression="count_records",
            created_by="owner-1",
            status=FormulaStatus.APPROVED,
            approved_by="approver-1",
            approved_at=datetime(2026, 1, 1),
        )
    )
    definition_repository.upsert_definition(
        context(tenant_id="tenant-2"),
        KPIDefinition(
            kpi_id="csat",
            tenant_id="tenant-2",
            name="CSAT",
            domain=KPIDomain.CUSTOMER_EXPERIENCE,
            owner_user_id="owner-2",
            steward_user_id="steward-2",
            created_by="owner-2",
        )
    )
    definition_repository.upsert_formula_version(
        context(tenant_id="tenant-2"),
        FormulaVersion(
            formula_version_id="tenant-2-formula",
            tenant_id="tenant-2",
            kpi_id="csat",
            version="1.0",
            expression="count_records",
            created_by="owner-2",
            status=FormulaStatus.APPROVED,
            approved_by="approver-2",
            approved_at=datetime(2026, 1, 1),
        )
    )
    return SQLiteKPICalculationResultRepository(database)


def result(tenant_id="tenant-1", result_id="result-1"):
    return KPICalculationResult(
        tenant_id=tenant_id,
        result_id=result_id,
        kpi_id="csat",
        formula_version_id="formula-1",
        formula_version_number="1.0",
        period_start=datetime(2026, 1, 1),
        period_end=datetime(2026, 1, 31),
        scope={
            "team": "support"
        },
        value=95.5,
        status=KPICalculationStatus.SUCCESS,
        data_quality_status="valid",
        source_reference="survey:test",
        calculation_run_id="run-1",
    )


def result_with_formula(formula_version_id):
    item = result()
    item.formula_version_id = formula_version_id
    return item


def source_backed_result_without_lineage():
    item = result()
    item.metadata = {
        "source_record_ids": ["source-1"],
        "source_references": ["survey:2026-03"],
        "source_types": ["survey"],
        "source_version": ["v1"],
    }
    return item


def test_result_repository_persists_and_reads_by_tenant(tmp_path):
    repo = create_repo(tmp_path)

    repo.save(
        context(),
        result()
    )
    persisted = repo.get_result(
        context(),
        "result-1"
    )

    assert persisted is not None
    assert persisted.tenant_id == "tenant-1"
    assert persisted.value == 95.5


def test_result_repository_lists_results_for_kpi(tmp_path):
    repo = create_repo(tmp_path)
    repo.save(context(), result(result_id="result-1"))
    repo.save(context(), result(result_id="result-2"))

    results = repo.list_results_for_kpi(
        context(),
        "csat"
    )

    assert [item.result_id for item in results] == ["result-1", "result-2"]


def test_result_repository_rejects_cross_tenant_save(tmp_path):
    repo = create_repo(tmp_path)

    with pytest.raises(PermissionError, match="tenant-scoped"):
        repo.save(
            context(tenant_id="tenant-1"),
            result(tenant_id="tenant-2")
        )


def test_result_repository_rejects_formula_from_another_tenant(tmp_path):
    repo = create_repo(tmp_path)

    with pytest.raises(ValueError, match="Formula version not found"):
        repo.save(
            context(),
            result_with_formula("tenant-2-formula")
        )


def test_result_repository_rejects_formula_for_another_kpi(tmp_path):
    repo = create_repo(tmp_path)

    with pytest.raises(ValueError, match="does not belong"):
        repo.save(
            context(),
            result_with_formula("qa-formula")
        )


def test_result_repository_rejects_nonexistent_formula_version(tmp_path):
    repo = create_repo(tmp_path)

    with pytest.raises(ValueError, match="Formula version not found"):
        repo.save(
            context(),
            result_with_formula("missing-formula")
        )


def test_result_repository_rejects_source_backed_result_without_lineage(tmp_path):
    repo = create_repo(tmp_path)

    with pytest.raises(ValueError, match="Source lineage is required"):
        repo.save(
            context(),
            source_backed_result_without_lineage()
        )


def test_result_repository_filters_cross_tenant_read(tmp_path):
    repo = create_repo(tmp_path)
    repo.save(context(), result())

    assert repo.get_result(context(tenant_id="tenant-2"), "result-1") is None


def test_result_access_requires_view_kpi_results_permission(tmp_path):
    repo = create_repo(tmp_path)
    repo.save(context(), result())
    unauthorized = TenantContext(
        tenant_id="tenant-1",
        user_id="user-1",
        roles=set(),
    )

    with pytest.raises(PermissionError, match="view_kpi_results"):
        repo.get_result(
            unauthorized,
            "result-1"
        )
