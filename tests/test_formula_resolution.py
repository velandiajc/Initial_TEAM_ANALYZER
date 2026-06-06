from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import FormulaStatus, FormulaVersion, KPIDefinition, KPIDomain
from app.services.database_service import DatabaseService
from app.services.formula_version_service import (
    FormulaConflictError,
    FormulaVersionService,
    MissingApprovedFormulaError,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)


def context(tenant_id="tenant-1"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )


def create_repo(tmp_path):
    database = DatabaseService(tmp_path / "governance.db")
    database.initialize()
    repo = SQLiteKPIDefinitionRepository(database)
    repo.upsert_definition(
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
    return repo


def formula(
    formula_version_id,
    version,
    effective_from,
    effective_to=None,
    status=FormulaStatus.APPROVED
):
    return FormulaVersion(
        formula_version_id=formula_version_id,
        tenant_id="tenant-1",
        kpi_id="csat",
        version=version,
        expression="count_records",
        created_by="owner-1",
        status=status,
        approved_by="approver-1" if status == FormulaStatus.APPROVED else None,
        approved_at=(
            datetime(2026, 1, 1)
            if status == FormulaStatus.APPROVED
            else None
        ),
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_approved_formula_selected_for_calculation_period(tmp_path):
    repo = create_repo(tmp_path)
    selected = formula(
        "formula-1",
        "1.0",
        datetime(2026, 1, 1),
        datetime(2026, 6, 30),
    )
    repo.upsert_formula_version(context(), selected)

    resolved = FormulaVersionService(repo).get_approved_formula_for_period(
        context(),
        "csat",
        datetime(2026, 3, 1),
        datetime(2026, 3, 31),
    )

    assert resolved.formula_version_id == "formula-1"


def test_correct_formula_version_selected_by_effective_date(tmp_path):
    repo = create_repo(tmp_path)
    repo.upsert_formula_version(
        context(),
        formula("formula-1", "1.0", datetime(2026, 1, 1), datetime(2026, 6, 30))
    )
    repo.upsert_formula_version(
        context(),
        formula("formula-2", "2.0", datetime(2026, 7, 1), datetime(2026, 12, 31))
    )

    resolved = FormulaVersionService(repo).get_approved_formula_for_period(
        context(),
        "csat",
        datetime(2026, 8, 1),
        datetime(2026, 8, 31),
    )

    assert resolved.version == "2.0"


def test_pending_formula_is_not_selected(tmp_path):
    repo = create_repo(tmp_path)
    repo.upsert_formula_version(
        context(),
        formula(
            "formula-1",
            "1.0",
            datetime(2026, 1, 1),
            datetime(2026, 12, 31),
            status=FormulaStatus.PENDING_APPROVAL,
        )
    )

    with pytest.raises(MissingApprovedFormulaError):
        FormulaVersionService(repo).get_approved_formula_for_period(
            context(),
            "csat",
            datetime(2026, 3, 1),
            datetime(2026, 3, 31),
        )


def test_missing_formula_is_rejected(tmp_path):
    repo = create_repo(tmp_path)

    with pytest.raises(MissingApprovedFormulaError):
        FormulaVersionService(repo).get_approved_formula_for_period(
            context(),
            "csat",
            datetime(2026, 3, 1),
            datetime(2026, 3, 31),
        )


def test_formula_outside_effective_period_is_rejected(tmp_path):
    repo = create_repo(tmp_path)
    repo.upsert_formula_version(
        context(),
        formula("formula-1", "1.0", datetime(2026, 1, 1), datetime(2026, 1, 31))
    )

    with pytest.raises(MissingApprovedFormulaError):
        FormulaVersionService(repo).get_approved_formula_for_period(
            context(),
            "csat",
            datetime(2026, 2, 1),
            datetime(2026, 2, 28),
        )


def test_overlapping_approved_formulas_are_rejected(tmp_path):
    repo = create_repo(tmp_path)
    repo.upsert_formula_version(
        context(),
        formula("formula-1", "1.0", datetime(2026, 1, 1), datetime(2026, 12, 31))
    )
    repo.upsert_formula_version(
        context(),
        formula("formula-2", "2.0", datetime(2026, 1, 1), datetime(2026, 12, 31))
    )

    with pytest.raises(FormulaConflictError):
        FormulaVersionService(repo).get_approved_formula_for_period(
            context(),
            "csat",
            datetime(2026, 3, 1),
            datetime(2026, 3, 31),
        )


def test_formula_retrieval_is_tenant_scoped(tmp_path):
    repo = create_repo(tmp_path)
    repo.upsert_formula_version(
        context(),
        formula("formula-1", "1.0", datetime(2026, 1, 1), datetime(2026, 12, 31))
    )

    assert repo.get_formula_version(context("tenant-2"), "formula-1") is None
