from datetime import datetime

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import FormulaVersion


class MissingApprovedFormulaError(ValueError):
    pass


class FormulaConflictError(ValueError):
    pass


class FormulaVersionService:
    def __init__(self, definition_repository):
        self.definition_repository = definition_repository

    def get_approved_formula_for_period(
        self,
        context: TenantContext | None,
        kpi_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> FormulaVersion:
        context = require_tenant_context(context)
        _validate_period(period_start, period_end)

        formulas = self.definition_repository.get_approved_formulas_for_period(
            context,
            kpi_id,
            period_start,
            period_end
        )

        if not formulas:
            raise MissingApprovedFormulaError(
                f"No approved formula found for KPI '{kpi_id}' in period."
            )

        if len(formulas) > 1:
            raise FormulaConflictError(
                f"Multiple approved formulas found for KPI '{kpi_id}' in period."
            )

        return formulas[0]

    def get_formula_lineage(
        self,
        context: TenantContext | None,
        kpi_id: str
    ) -> list[FormulaVersion]:
        context = require_tenant_context(context)

        return self.definition_repository.get_formula_lineage(
            context,
            kpi_id
        )

    def validate_no_effective_period_conflict(
        self,
        context: TenantContext | None,
        formula_version: FormulaVersion
    ) -> None:
        context = require_tenant_context(context)

        if context.tenant_id != formula_version.tenant_id:
            raise PermissionError("Formula tenant does not match context.")

        if not formula_version.is_approved():
            return

        approved_formulas = [
            formula
            for formula in self.definition_repository.get_formula_lineage(
                context,
                formula_version.kpi_id
            )
            if formula.is_approved()
            and formula.formula_version_id != formula_version.formula_version_id
        ]

        for existing in approved_formulas:
            if formula_version.overlaps_effective_period(existing):
                raise FormulaConflictError(
                    "Approved formula effective period overlaps existing formula."
                )


def _validate_period(
    period_start: datetime,
    period_end: datetime
) -> None:
    if period_start > period_end:
        raise ValueError("period_start must be before or equal to period_end.")
