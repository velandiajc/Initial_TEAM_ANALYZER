from datetime import datetime

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.kpi import FormulaStatus, FormulaVersion, KPIDefinition, KPIDomain
from app.services.database_service import DatabaseService
from app.services.formula_version_service import (
    FormulaConflictError,
    FormulaVersionService,
)
from app.services.sqlite_kpi_definition_repository import (
    SQLiteKPIDefinitionRepository,
)


def context():
    return TenantContext(
        tenant_id="tenant-1",
        user_id="owner-1",
        roles={GovernanceRole.KPI_OWNER.value},
    )


def repository(tmp_path):
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


def approved_formula(
    formula_version_id,
    version,
    effective_from,
    effective_to=None,
    supersedes_formula_version_id=None
):
    return FormulaVersion(
        formula_version_id=formula_version_id,
        tenant_id="tenant-1",
        kpi_id="csat",
        version=version,
        expression="count_records",
        created_by="owner-1",
        status=FormulaStatus.APPROVED,
        approved_by="approver-1",
        approved_at=datetime(2026, 1, 1),
        effective_from=effective_from,
        effective_to=effective_to,
        supersedes_formula_version_id=supersedes_formula_version_id,
    )


def test_formula_effective_date_validation():
    with pytest.raises(ValueError, match="effective_from"):
        approved_formula(
            "formula-1",
            "1.0",
            datetime(2026, 2, 1),
            datetime(2026, 1, 1),
        )


def test_approved_formula_is_immutable_after_approval():
    formula = FormulaVersion(
        formula_version_id="formula-1",
        tenant_id="tenant-1",
        kpi_id="csat",
        version="1.0",
        expression="count_records",
        created_by="owner-1",
        effective_from=datetime(2026, 1, 1),
    )

    formula.approve("approver-1")

    with pytest.raises(AttributeError, match="immutable"):
        formula.expression = "qa_average"


def test_repository_rejects_approved_formula_mutation(tmp_path):
    repo = repository(tmp_path)
    formula = approved_formula(
        "formula-1",
        "1.0",
        datetime(2026, 1, 1),
        datetime(2026, 12, 31),
    )
    repo.upsert_formula_version(context(), formula)
    mutated = approved_formula(
        "formula-1",
        "1.0",
        datetime(2026, 1, 1),
        datetime(2026, 12, 31),
    )
    object.__setattr__(
        mutated,
        "expression",
        "qa_average"
    )

    with pytest.raises(PermissionError, match="immutable"):
        repo.upsert_formula_version(context(), mutated)


def test_formula_lineage_remains_retrievable(tmp_path):
    repo = repository(tmp_path)
    first = approved_formula(
        "formula-1",
        "1.0",
        datetime(2026, 1, 1),
        datetime(2026, 6, 30),
    )
    second = approved_formula(
        "formula-2",
        "2.0",
        datetime(2026, 7, 1),
        None,
        supersedes_formula_version_id="formula-1",
    )
    repo.upsert_formula_version(context(), first)
    repo.upsert_formula_version(context(), second)

    lineage = FormulaVersionService(repo).get_formula_lineage(
        context(),
        "csat"
    )

    assert [formula.version for formula in lineage] == ["1.0", "2.0"]
    assert lineage[1].supersedes_formula_version_id == "formula-1"


def test_formula_overlap_detection(tmp_path):
    repo = repository(tmp_path)
    first = approved_formula(
        "formula-1",
        "1.0",
        datetime(2026, 1, 1),
        datetime(2026, 6, 30),
    )
    overlapping = approved_formula(
        "formula-2",
        "2.0",
        datetime(2026, 6, 1),
        datetime(2026, 12, 31),
    )
    repo.upsert_formula_version(context(), first)
    repo.upsert_formula_version(context(), overlapping)

    with pytest.raises(FormulaConflictError, match="overlaps"):
        FormulaVersionService(repo).validate_no_effective_period_conflict(
            context(),
            overlapping
        )
