from typing import Any

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
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
        rbac_service: RBACService | None = None
    ):
        self.risk_repository = risk_repository
        self.rule_version_service = rule_version_service
        self.handler_registry = handler_registry
        self.audit_service = audit_service
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
            action="RISK_ASSESSMENT_REQUESTED",
            request=assessment_request,
            status="requested",
        )

        try:
            self.rbac_service.require_permission(
                context,
                KPIPermission.ASSESS_RISK
            )
            self._validate_period(assessment_request)
            self._audit(
                context,
                action="RISK_ASSESSMENT_STARTED",
                request=assessment_request,
                status="started",
            )

            definition = self.risk_repository.get_definition(
                context,
                assessment_request.risk_definition_id
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
                    assessment_request.risk_definition_id,
                    assessment_request.period_start,
                    assessment_request.period_end
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
                request=assessment_request,
                rule_version_id=rule_version.rule_version_id,
                status="selected",
            )

            handler = self.handler_registry.require_handler(
                rule_version.handler_key
            )
            evaluation = handler.evaluate(
                assessment_request,
                rule_version
            )
            result = RiskAssessmentResult(
                tenant_id=context.tenant_id,
                risk_definition_id=assessment_request.risk_definition_id,
                rule_version_id=rule_version.rule_version_id,
                rule_version_number=rule_version.version,
                entity_type=assessment_request.entity_type,
                entity_id=assessment_request.entity_id,
                period_start=assessment_request.period_start,
                period_end=assessment_request.period_end,
                risk_level=evaluation.risk_level,
                status=RiskAssessmentStatus.SUCCESS,
                reason=evaluation.reason,
                evidence={
                    **evaluation.evidence,
                    "handler_key": rule_version.handler_key,
                    "rule_triggered": evaluation.triggered,
                },
                source_reference=assessment_request.source_reference,
                assessment_run_id=assessment_request.assessment_run_id,
                metadata={
                    "input_metric_names": sorted(
                        assessment_request.metric_values.keys()
                    ),
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
                action="RISK_ASSESSMENT_COMPLETED",
                request=assessment_request,
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
                action="RISK_ASSESSMENT_FAILED",
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
        self.rbac_service.require_permission(
            context,
            KPIPermission.VIEW_RISK_RESULTS
        )
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
        self.rbac_service.require_permission(
            context,
            KPIPermission.VIEW_RISK_RESULTS
        )
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
            action="RISK_ASSESSMENT_REJECTED",
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
            entity_type="risk_assessment",
            entity_id=request.risk_definition_id,
            metadata=metadata,
        )
