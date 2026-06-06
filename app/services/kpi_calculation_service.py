from typing import Any

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import FormulaVersion, KPILifecycle
from app.models.kpi_calculation import (
    FormulaHandlerResult,
    KPICalculationRequest,
    KPICalculationResult,
    KPICalculationStatus,
)
from app.services.formula_version_service import (
    FormulaConflictError,
    MissingApprovedFormulaError,
)


class KPICalculationRejectedError(ValueError):
    def __init__(
        self,
        message: str,
        status: KPICalculationStatus = KPICalculationStatus.REJECTED
    ):
        super().__init__(message)
        self.status = status


class KPICalculationService:
    def __init__(
        self,
        definition_repository,
        formula_version_service,
        formula_handler_registry,
        result_repository,
        audit_service,
        rbac_service: RBACService | None = None
    ):
        self.definition_repository = definition_repository
        self.formula_version_service = formula_version_service
        self.formula_handler_registry = formula_handler_registry
        self.result_repository = result_repository
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def calculate_kpi(
        self,
        context: TenantContext | None,
        calculation_request: KPICalculationRequest
    ) -> KPICalculationResult:
        context = require_tenant_context(context)
        run_id = calculation_request.calculation_run_id
        formula_version: FormulaVersion | None = None

        self._audit(
            context,
            action="CALCULATION_REQUESTED",
            request=calculation_request,
            status="requested",
        )

        try:
            self.rbac_service.require_permission(
                context,
                KPIPermission.CALCULATE_KPI
            )
            self._validate_period(calculation_request)
            self._validate_source_tenant(
                context,
                calculation_request
            )
            self._audit(
                context,
                action="CALCULATION_STARTED",
                request=calculation_request,
                status="started",
            )

            definition = self.definition_repository.get_definition(
                context,
                calculation_request.kpi_id
            )

            if definition is None:
                raise KPICalculationRejectedError(
                    f"KPI definition not found: {calculation_request.kpi_id}",
                    KPICalculationStatus.REJECTED
                )

            self._validate_tenant_boundary(
                context.tenant_id,
                definition.tenant_id,
                "KPI definition"
            )

            if definition.lifecycle != KPILifecycle.ACTIVE:
                raise KPICalculationRejectedError(
                    "KPI must be active before calculation.",
                    KPICalculationStatus.FAILED_VALIDATION
                )

            formula_version = (
                self.formula_version_service.get_approved_formula_for_period(
                    context,
                    calculation_request.kpi_id,
                    calculation_request.period_start,
                    calculation_request.period_end
                )
            )
            self._validate_tenant_boundary(
                context.tenant_id,
                formula_version.tenant_id,
                "formula version"
            )
            self._audit(
                context,
                action="FORMULA_SELECTED",
                request=calculation_request,
                formula_version_id=formula_version.formula_version_id,
                status="selected",
            )

            handler = self.formula_handler_registry.require_handler(
                formula_version.expression
            )
            handler_result = self._normalize_handler_result(
                handler.calculate(
                    calculation_request,
                    formula_version
                ),
                calculation_request
            )
            result = KPICalculationResult(
                tenant_id=context.tenant_id,
                kpi_id=calculation_request.kpi_id,
                formula_version_id=formula_version.formula_version_id,
                formula_version_number=formula_version.version,
                period_start=calculation_request.period_start,
                period_end=calculation_request.period_end,
                scope=calculation_request.scope,
                value=handler_result.value,
                status=KPICalculationStatus.SUCCESS,
                data_quality_status=handler_result.data_quality_status,
                source_reference=handler_result.source_reference,
                calculation_run_id=run_id,
                metadata=handler_result.metadata,
            )
            self._validate_tenant_boundary(
                context.tenant_id,
                result.tenant_id,
                "calculation result"
            )
            self.result_repository.save(
                context,
                result
            )
            self._audit(
                context,
                action="CALCULATION_COMPLETED",
                request=calculation_request,
                formula_version_id=formula_version.formula_version_id,
                result_id=result.result_id,
                status=result.status.value,
            )

            return result

        except MissingApprovedFormulaError as exc:
            self._audit_rejection(
                context,
                calculation_request,
                exc,
                KPICalculationStatus.MISSING_FORMULA,
                formula_version
            )
            raise
        except FormulaConflictError as exc:
            self._audit_rejection(
                context,
                calculation_request,
                exc,
                KPICalculationStatus.FORMULA_CONFLICT,
                formula_version
            )
            raise
        except (KPICalculationRejectedError, PermissionError, KeyError, ValueError) as exc:
            status = getattr(
                exc,
                "status",
                KPICalculationStatus.REJECTED
            )
            self._audit_rejection(
                context,
                calculation_request,
                exc,
                status,
                formula_version
            )
            raise
        except Exception as exc:
            self._audit(
                context,
                action="CALCULATION_FAILED",
                request=calculation_request,
                formula_version_id=(
                    formula_version.formula_version_id
                    if formula_version
                    else ""
                ),
                status=KPICalculationStatus.CALCULATION_ERROR.value,
                reason=str(exc),
            )
            raise

    def get_result(
        self,
        context: TenantContext | None,
        result_id: str
    ) -> KPICalculationResult | None:
        context = require_tenant_context(context)
        result = self.result_repository.get_result(
            context,
            result_id
        )

        if result is not None:
            self._audit_result_viewed(
                context,
                result
            )

        return result

    def list_results_for_kpi(
        self,
        context: TenantContext | None,
        kpi_id: str
    ) -> list[KPICalculationResult]:
        context = require_tenant_context(context)
        results = self.result_repository.list_results_for_kpi(
            context,
            kpi_id
        )

        for result in results:
            self._audit_result_viewed(
                context,
                result
            )

        return results

    def _validate_period(
        self,
        calculation_request: KPICalculationRequest
    ) -> None:
        if calculation_request.period_start > calculation_request.period_end:
            raise KPICalculationRejectedError(
                "period_start must be before or equal to period_end.",
                KPICalculationStatus.FAILED_VALIDATION
            )

    def _validate_source_tenant(
        self,
        context: TenantContext,
        calculation_request: KPICalculationRequest
    ) -> None:
        self._validate_tenant_boundary(
            context.tenant_id,
            calculation_request.source_data.tenant_id,
            "source data"
        )

    def _validate_tenant_boundary(
        self,
        expected_tenant_id: str,
        actual_tenant_id: str,
        boundary_name: str
    ) -> None:
        if expected_tenant_id != actual_tenant_id:
            raise PermissionError(
                f"{boundary_name} tenant does not match context."
            )

    def _normalize_handler_result(
        self,
        value,
        calculation_request: KPICalculationRequest
    ) -> FormulaHandlerResult:
        if isinstance(value, FormulaHandlerResult):
            return value

        return FormulaHandlerResult(
            value=float(value),
            source_reference=calculation_request.source_data.source_reference,
        )

    def _audit_rejection(
        self,
        context: TenantContext,
        calculation_request: KPICalculationRequest,
        exc: Exception,
        status: KPICalculationStatus,
        formula_version: FormulaVersion | None = None
    ) -> None:
        self._audit(
            context,
            action="CALCULATION_REJECTED",
            request=calculation_request,
            formula_version_id=(
                formula_version.formula_version_id
                if formula_version
                else ""
            ),
            status=status.value,
            reason=str(exc),
        )

    def _audit_result_viewed(
        self,
        context: TenantContext,
        result: KPICalculationResult
    ) -> None:
        self.audit_service.record(
            context,
            action="RESULT_VIEWED",
            entity_type="kpi_calculation_result",
            entity_id=result.result_id,
            metadata={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "kpi_id": result.kpi_id,
                "formula_version_id": result.formula_version_id,
                "calculation_run_id": result.calculation_run_id,
                "result_id": result.result_id,
                "status": result.status.value,
                "reason": "",
            },
        )

    def _audit(
        self,
        context: TenantContext,
        action: str,
        request: KPICalculationRequest,
        status: str,
        formula_version_id: str = "",
        result_id: str = "",
        reason: str = ""
    ) -> None:
        self.audit_service.record(
            context,
            action=action,
            entity_type="kpi_calculation",
            entity_id=request.kpi_id,
            metadata={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "kpi_id": request.kpi_id,
                "formula_version_id": formula_version_id,
                "calculation_run_id": request.calculation_run_id,
                "result_id": result_id,
                "status": status,
                "reason": reason,
            },
        )
