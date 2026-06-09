from dataclasses import replace
from typing import Any

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi_calculation import (
    KPICalculationResult,
    KPICalculationStatus,
)
from app.models.risk import (
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskDefinitionLifecycle,
    RiskLevel,
    RiskRuleVersion,
)
from app.services.risk_rule_version_service import (
    MissingApprovedActiveRiskRuleError,
    RiskRuleConflictError,
)


class RiskAssessmentRejectedError(ValueError):
    def __init__(
        self,
        message: str,
        status: RiskAssessmentStatus = RiskAssessmentStatus.REJECTED
    ):
        super().__init__(message)
        self.status = status


class RiskAssessmentService:
    def __init__(
        self,
        risk_repository,
        rule_version_service,
        handler_registry,
        audit_service,
        kpi_result_repository=None,
        rbac_service: RBACService | None = None
    ):
        self.risk_repository = risk_repository
        self.rule_version_service = rule_version_service
        self.handler_registry = handler_registry
        self.audit_service = audit_service
        self.kpi_result_repository = kpi_result_repository
        self.rbac_service = rbac_service or RBACService()

    def assess_risk(
        self,
        context: TenantContext | None,
        assessment_request: RiskAssessmentRequest
    ) -> RiskAssessmentResult:
        context = require_tenant_context(context)
        rule_version: RiskRuleVersion | None = None

        self._audit(
            context,
            action="RISK_EVALUATION_REQUESTED",
            request=assessment_request,
            status="requested",
        )

        try:
            self.rbac_service.require_permission(
                context,
                KPIPermission.EVALUATE_RISK
            )
            self._validate_period(assessment_request)
            kpi_results = self._resolve_kpi_results(
                context,
                assessment_request
            )
            resolved_request = replace(
                assessment_request,
                metric_values=self._metric_values_from_kpi_results(kpi_results)
            )
            lineage = self._build_lineage(
                assessment_request,
                kpi_results
            )
            self._audit(
                context,
                action="RISK_EVALUATION_STARTED",
                request=resolved_request,
                status="started",
            )

            definition = self.risk_repository.get_definition(
                context,
                resolved_request.risk_definition_id
            )

            if definition is None:
                raise RiskAssessmentRejectedError(
                    "Risk definition not found.",
                    RiskAssessmentStatus.REJECTED
                )

            self._validate_tenant_boundary(
                context.tenant_id,
                definition.tenant_id,
                "risk definition"
            )

            if definition.lifecycle != RiskDefinitionLifecycle.ACTIVE:
                raise RiskAssessmentRejectedError(
                    "Risk definition must be active before assessment.",
                    RiskAssessmentStatus.FAILED_VALIDATION
                )

            rule_version = (
                self.rule_version_service.get_approved_active_rule_for_period(
                    context,
                    resolved_request.risk_definition_id,
                    resolved_request.period_start,
                    resolved_request.period_end
                )
            )
            self._validate_tenant_boundary(
                context.tenant_id,
                rule_version.tenant_id,
                "risk rule version"
            )
            self._audit(
                context,
                action="RISK_RULE_SELECTED",
                request=resolved_request,
                rule_version_id=rule_version.rule_version_id,
                status="selected",
            )

            handler = self.handler_registry.require_handler(
                rule_version.handler_key
            )
            evaluation = handler.evaluate(
                resolved_request,
                rule_version
            )
            result = RiskAssessmentResult(
                tenant_id=context.tenant_id,
                risk_definition_id=resolved_request.risk_definition_id,
                rule_version_id=rule_version.rule_version_id,
                rule_version_number=rule_version.version,
                entity_type=resolved_request.entity_type,
                entity_id=resolved_request.entity_id,
                period_start=resolved_request.period_start,
                period_end=resolved_request.period_end,
                risk_score=evaluation.risk_score,
                risk_level=evaluation.risk_level,
                status=RiskAssessmentStatus.SUCCESS,
                reason=evaluation.reason,
                evidence={
                    **evaluation.evidence,
                    "handler_key": rule_version.handler_key,
                    "rule_triggered": evaluation.triggered,
                },
                source_reference=self._source_reference_for_result(
                    resolved_request,
                    kpi_results
                ),
                assessment_run_id=resolved_request.assessment_run_id,
                risk_definition_version=str(
                    definition.metadata.get("version", "1.0")
                ),
                kpi_result_ids=lineage["kpi_result_ids"],
                formula_versions=lineage["formula_versions"],
                source_record_ids=lineage["source_record_ids"],
                source_validation_lineage=lineage["source_validation_lineage"],
                lineage_id=lineage["lineage_id"],
                metadata={
                    "input_metric_names": sorted(resolved_request.metric_values.keys()),
                },
            )
            self._validate_tenant_boundary(
                context.tenant_id,
                result.tenant_id,
                "risk assessment result"
            )
            self.risk_repository.save_result(context, result)
            self._audit(
                context,
                action="RISK_EVALUATION_COMPLETED",
                request=resolved_request,
                rule_version_id=rule_version.rule_version_id,
                result_id=result.result_id,
                status=result.status.value,
                risk_level=result.risk_level.value,
            )

            return result

        except MissingApprovedActiveRiskRuleError as exc:
            self._audit_rejection(
                context,
                assessment_request,
                exc,
                RiskAssessmentStatus.MISSING_RULE,
                rule_version
            )
            raise
        except RiskRuleConflictError as exc:
            self._audit_rejection(
                context,
                assessment_request,
                exc,
                RiskAssessmentStatus.RULE_CONFLICT,
                rule_version
            )
            raise
        except PermissionError as exc:
            self._audit_access_denied(
                context,
                assessment_request,
                str(exc)
            )
            raise
        except (RiskAssessmentRejectedError, PermissionError, KeyError, ValueError) as exc:
            status = getattr(exc, "status", RiskAssessmentStatus.REJECTED)
            self._audit_rejection(
                context,
                assessment_request,
                exc,
                status,
                rule_version
            )
            raise
        except Exception as exc:
            self._audit(
                context,
                action="RISK_EVALUATION_FAILED",
                request=assessment_request,
                rule_version_id=(
                    rule_version.rule_version_id
                    if rule_version
                    else ""
                ),
                status=RiskAssessmentStatus.EXECUTION_ERROR.value,
                reason=str(exc),
            )
            raise

    def get_result(
        self,
        context: TenantContext | None,
        result_id: str
    ) -> RiskAssessmentResult | None:
        context = require_tenant_context(context)
        try:
            self.rbac_service.require_permission(
                context,
                KPIPermission.VIEW_RISK_RESULTS
            )
        except PermissionError as exc:
            self._audit_access_denied_for_result(
                context,
                result_id,
                str(exc)
            )
            raise
        result = self.risk_repository.get_result(context, result_id)

        if result is not None:
            self._audit_result_viewed(context, result)

        return result

    def list_results_for_definition(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> list[RiskAssessmentResult]:
        context = require_tenant_context(context)
        try:
            self.rbac_service.require_permission(
                context,
                KPIPermission.VIEW_RISK_RESULTS
            )
        except PermissionError as exc:
            self._audit_access_denied_for_result(
                context,
                risk_definition_id,
                str(exc)
            )
            raise
        results = self.risk_repository.list_results_for_definition(
            context,
            risk_definition_id
        )

        for result in results:
            self._audit_result_viewed(context, result)

        return results

    def _validate_period(
        self,
        assessment_request: RiskAssessmentRequest
    ) -> None:
        if assessment_request.period_start > assessment_request.period_end:
            raise RiskAssessmentRejectedError(
                "period_start must be before or equal to period_end.",
                RiskAssessmentStatus.FAILED_VALIDATION
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

    def _resolve_kpi_results(
        self,
        context: TenantContext,
        assessment_request: RiskAssessmentRequest
    ) -> list[KPICalculationResult]:
        if not assessment_request.kpi_result_ids and not assessment_request.kpi_results:
            raise RiskAssessmentRejectedError(
                "Governed KPI Result reference is required for risk evaluation.",
                RiskAssessmentStatus.FAILED_VALIDATION
            )

        results: list[KPICalculationResult] = []

        if assessment_request.kpi_results:
            results.extend(assessment_request.kpi_results)

        if assessment_request.kpi_result_ids:
            if self.kpi_result_repository is None:
                raise RiskAssessmentRejectedError(
                    "KPI result repository is required for risk evaluation.",
                    RiskAssessmentStatus.FAILED_VALIDATION
                )

            for result_id in assessment_request.kpi_result_ids:
                result = self.kpi_result_repository.get_result(context, result_id)

                if result is None:
                    raise RiskAssessmentRejectedError(
                        f"KPI Result not found or not accessible: {result_id}",
                        RiskAssessmentStatus.FAILED_VALIDATION
                    )

                results.append(result)

        unique_results = {
            result.result_id: result
            for result in results
        }

        for result in unique_results.values():
            self._validate_kpi_result(context, assessment_request, result)

        return list(unique_results.values())

    def _validate_kpi_result(
        self,
        context: TenantContext,
        assessment_request: RiskAssessmentRequest,
        result: KPICalculationResult
    ) -> None:
        self._validate_tenant_boundary(
            context.tenant_id,
            result.tenant_id,
            "KPI result"
        )

        if result.status != KPICalculationStatus.SUCCESS:
            raise RiskAssessmentRejectedError(
                "KPI Result must be successful before risk evaluation.",
                RiskAssessmentStatus.FAILED_VALIDATION
            )

        if result.value is None:
            raise RiskAssessmentRejectedError(
                "KPI Result must include a trusted numeric value.",
                RiskAssessmentStatus.FAILED_VALIDATION
            )

        if str(result.data_quality_status).strip().lower() not in {
            "valid",
            "trusted",
        }:
            raise RiskAssessmentRejectedError(
                "KPI Result must have trusted data quality.",
                RiskAssessmentStatus.FAILED_VALIDATION
            )

        if (
            result.period_start < assessment_request.period_start
            or result.period_end > assessment_request.period_end
        ):
            raise RiskAssessmentRejectedError(
                "KPI Result is outside the risk evaluation period.",
                RiskAssessmentStatus.FAILED_VALIDATION
            )

    def _metric_values_from_kpi_results(
        self,
        kpi_results: list[KPICalculationResult]
    ) -> dict[str, float]:
        return {
            result.kpi_id: float(result.value)
            for result in kpi_results
            if result.value is not None
        }

    def _build_lineage(
        self,
        assessment_request: RiskAssessmentRequest,
        kpi_results: list[KPICalculationResult]
    ) -> dict[str, Any]:
        kpi_result_ids = [
            result.result_id
            for result in kpi_results
        ]
        formula_versions = [
            {
                "kpi_id": result.kpi_id,
                "formula_version_id": result.formula_version_id,
                "formula_version_number": result.formula_version_number,
            }
            for result in kpi_results
        ]
        source_record_ids = self._collect_metadata_values(
            kpi_results,
            "source_record_ids"
        )
        source_references = [
            reference
            for reference in self._collect_metadata_values(
                kpi_results,
                "source_references"
            )
            if reference
        ]
        source_references.extend([
            result.source_reference
            for result in kpi_results
            if result.source_reference
        ])
        lineage_values = self._collect_metadata_values(
            kpi_results,
            "lineage_id"
        )
        source_validation_lineage = {
            "data_quality_status": sorted({
                result.data_quality_status
                for result in kpi_results
                if result.data_quality_status
            }),
            "source_validation_status": self._collect_metadata_values(
                kpi_results,
                "source_validation_status"
            ),
            "source_quality_summary": [
                result.metadata.get("source_quality_summary")
                for result in kpi_results
                if result.metadata.get("source_quality_summary")
            ],
            "source_references": sorted(set(source_references)),
            "lineage_id": lineage_values,
        }

        return {
            "kpi_result_ids": kpi_result_ids,
            "formula_versions": formula_versions,
            "source_record_ids": source_record_ids,
            "source_validation_lineage": source_validation_lineage,
            "lineage_id": (
                "|".join(lineage_values)
                if lineage_values
                else f"risk:{assessment_request.assessment_run_id}"
            ),
        }

    def _collect_metadata_values(
        self,
        kpi_results: list[KPICalculationResult],
        key: str
    ) -> list[str]:
        values: list[str] = []

        for result in kpi_results:
            raw_value = result.metadata.get(key)

            if raw_value is None:
                continue

            if isinstance(raw_value, list):
                values.extend([
                    str(item)
                    for item in raw_value
                    if str(item).strip()
                ])
                continue

            if str(raw_value).strip():
                values.append(str(raw_value))

        return sorted(set(values))

    def _source_reference_for_result(
        self,
        assessment_request: RiskAssessmentRequest,
        kpi_results: list[KPICalculationResult]
    ) -> str:
        if assessment_request.source_reference:
            return assessment_request.source_reference

        references = [
            result.source_reference
            for result in kpi_results
            if result.source_reference
        ]

        return ",".join(sorted(set(references)))

    def _audit_rejection(
        self,
        context: TenantContext,
        assessment_request: RiskAssessmentRequest,
        exc: Exception,
        status: RiskAssessmentStatus,
        rule_version: RiskRuleVersion | None = None
    ) -> None:
        self._audit(
            context,
            action="RISK_EVALUATION_REJECTED",
            request=assessment_request,
            rule_version_id=(
                rule_version.rule_version_id
                if rule_version
                else ""
            ),
            status=status.value,
            reason=str(exc),
        )

    def _audit_result_viewed(
        self,
        context: TenantContext,
        result: RiskAssessmentResult
    ) -> None:
        self.audit_service.record(
            context,
            action="RISK_RESULT_VIEWED",
            entity_type="risk_assessment_result",
            entity_id=result.result_id,
            metadata={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "risk_definition_id": result.risk_definition_id,
                "rule_version_id": result.rule_version_id,
                "assessment_run_id": result.assessment_run_id,
                "result_id": result.result_id,
                "status": result.status.value,
                "risk_level": result.risk_level.value,
                "reason": "",
            },
        )

    def _audit(
        self,
        context: TenantContext,
        action: str,
        request: RiskAssessmentRequest,
        status: str,
        rule_version_id: str = "",
        result_id: str = "",
        risk_level: RiskLevel | str = "",
        reason: str = ""
    ) -> None:
        metadata: dict[str, Any] = {
            "tenant_id": context.tenant_id,
            "user_id": context.user_id,
            "risk_definition_id": request.risk_definition_id,
            "rule_version_id": rule_version_id,
            "assessment_run_id": request.assessment_run_id,
            "result_id": result_id,
            "status": status,
            "risk_level": getattr(risk_level, "value", risk_level),
            "reason": reason,
            "entity_type": request.entity_type,
        }
        self.audit_service.record(
            context,
            action=action,
            entity_type="risk_evaluation",
            entity_id=request.risk_definition_id,
            metadata=metadata,
        )

    def _audit_access_denied(
        self,
        context: TenantContext,
        request: RiskAssessmentRequest,
        reason: str
    ) -> None:
        self._audit(
            context,
            action="RISK_ACCESS_DENIED",
            request=request,
            status="access_denied",
            reason=reason,
        )

    def _audit_access_denied_for_result(
        self,
        context: TenantContext,
        entity_id: str,
        reason: str
    ) -> None:
        self.audit_service.record(
            context,
            action="RISK_ACCESS_DENIED",
            entity_type="risk_result_access",
            entity_id=entity_id,
            metadata={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "status": "access_denied",
                "reason": reason,
            },
        )
