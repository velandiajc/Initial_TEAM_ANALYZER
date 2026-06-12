import hashlib

from app.application.operational_impact.services._service import (
    OperationalImpactServiceSupport,
)
from app.core.permissions import OperationalImpactPermission
from app.domain.operational_impact import (
    ImpactGovernanceStatus,
    OperationalImpactAssessment,
    OperationalImpactAuditEvent,
)
from app.domain.operational_impact.entities import new_id
from app.domain.operational_impact.rules import (
    classify_impact,
    normalize_factor_score,
)
from app.models.kpi_calculation import KPICalculationStatus
from app.models.risk import RiskAssessmentStatus


class OperationalImpactAssessmentService(OperationalImpactServiceSupport):
    def __init__(
        self,
        definition_repository,
        factor_repository,
        assessment_repository,
        kpi_result_repository,
        risk_repository,
        audit_service,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.definition_repository = definition_repository
        self.factor_repository = factor_repository
        self.assessment_repository = assessment_repository
        self.kpi_result_repository = kpi_result_repository
        self.risk_repository = risk_repository

    def calculate_impact(self, context, request, impact_assessment_id=None):
        context = self.context(context)
        try:
            self.require_permission(
                context,
                OperationalImpactPermission.CALCULATE_OPERATIONAL_IMPACT,
                "operational_impact_assessment",
                impact_assessment_id or "new",
            )
            definition = self.definition_repository.get_active(
                context,
                request.impact_definition_id,
            )
            if definition is None:
                raise ValueError("Active Operational Impact definition required.")
            factors = self.factor_repository.list_active_for_definition(
                context,
                definition.impact_definition_id,
                definition.impact_definition_version,
            )
            if not 5 <= len(factors) <= 8:
                raise ValueError(
                    "Operational Impact calculation requires 5 to 8 "
                    "active governed factors."
                )
            total_weight = sum(factor.weight for factor in factors)
            if abs(total_weight - 1.0) > 0.0001:
                raise ValueError("Active factor weights must total 1.0.")

            kpi_results = self._resolve_kpi_results(context, request)
            risk_results = self._resolve_risk_results(context, request)
            factor_scores = {}
            for factor in factors:
                value = self._governed_factor_value(
                    factor,
                    kpi_results,
                    risk_results,
                )
                factor_scores[factor.impact_factor_id] = (
                    normalize_factor_score(
                        value,
                        factor.threshold_min,
                        factor.threshold_max,
                        factor.direction,
                    )
                )
            impact_score = round(sum(
                factor_scores[factor.impact_factor_id] * factor.weight
                for factor in factors
            ), 4)
            lineage_id = self._lineage(
                context,
                definition,
                factors,
                kpi_results,
                risk_results,
            )
            assessment = OperationalImpactAssessment(
                impact_assessment_id=impact_assessment_id or new_id(),
                tenant_id=context.tenant_id,
                impact_definition_id=definition.impact_definition_id,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                assessment_period_start=request.assessment_period_start,
                assessment_period_end=request.assessment_period_end,
                impact_score=impact_score,
                impact_level=classify_impact(impact_score),
                impact_definition_version=(
                    definition.impact_definition_version
                ),
                impact_factor_ids=tuple(
                    factor.impact_factor_id
                    for factor in factors
                ),
                impact_factor_versions={
                    factor.impact_factor_id: factor.impact_factor_version
                    for factor in factors
                },
                threshold_versions={
                    factor.impact_factor_id: factor.threshold_version
                    for factor in factors
                },
                weight_snapshots={
                    factor.impact_factor_id: factor.weight
                    for factor in factors
                },
                factor_score_snapshots=factor_scores,
                source_kpi_result_ids=tuple(
                    result.result_id
                    for result in kpi_results
                ),
                source_risk_result_ids=tuple(
                    result.result_id
                    for result in risk_results
                ),
                lineage_id=lineage_id,
                created_by=context.user_id,
            )
            self.assessment_repository.save(context, assessment)
            self.audit(
                context,
                OperationalImpactAuditEvent.OPERATIONAL_IMPACT_CALCULATED,
                "operational_impact_assessment",
                assessment.impact_assessment_id,
                {
                    "impact_definition_id": assessment.impact_definition_id,
                    "impact_definition_version": (
                        assessment.impact_definition_version
                    ),
                    "impact_factor_ids": list(
                        assessment.impact_factor_ids
                    ),
                    "source_kpi_result_ids": list(
                        assessment.source_kpi_result_ids
                    ),
                    "source_risk_result_ids": list(
                        assessment.source_risk_result_ids
                    ),
                    "impact_score": assessment.impact_score,
                    "impact_level": assessment.impact_level.value,
                    "lineage_id": assessment.lineage_id,
                },
            )
            return assessment
        except PermissionError:
            raise
        except ValueError as exc:
            self.audit(
                context,
                OperationalImpactAuditEvent.OPERATIONAL_IMPACT_REJECTED,
                "operational_impact_assessment",
                impact_assessment_id or "new",
                {"reason": str(exc)},
            )
            raise
        except Exception as exc:
            self.audit(
                context,
                OperationalImpactAuditEvent.OPERATIONAL_IMPACT_CALCULATION_FAILED,
                "operational_impact_assessment",
                impact_assessment_id or "new",
                {"reason": str(exc)},
            )
            raise

    def get_assessment(self, context, assessment_id):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.VIEW_OPERATIONAL_IMPACT,
            "operational_impact_assessment",
            assessment_id,
        )
        assessment = self.assessment_repository.get_by_id(
            context,
            assessment_id,
        )
        self.require_entity(
            context,
            assessment,
            "operational_impact_assessment",
            assessment_id,
        )
        self.audit(
            context,
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_VIEWED,
            "operational_impact_assessment",
            assessment_id,
            {
                "impact_definition_id": assessment.impact_definition_id,
                "impact_level": assessment.impact_level.value,
            },
        )
        return assessment

    def _resolve_kpi_results(self, context, request):
        results = []
        for result_id in request.source_kpi_result_ids:
            result = self.kpi_result_repository.get_result(context, result_id)
            self.require_entity(
                context,
                result,
                "kpi_calculation_result",
                result_id,
            )
            if result.tenant_id != context.tenant_id:
                raise PermissionError("KPI Result tenant mismatch.")
            if result.status != KPICalculationStatus.SUCCESS:
                raise ValueError("KPI Result must be successful.")
            if result.value is None:
                raise ValueError("KPI Result requires a numeric value.")
            if result.data_quality_status.lower() not in {"valid", "trusted"}:
                raise ValueError("KPI Result data quality must be trusted.")
            self._validate_period_and_entity(result, request)
            if not self._source_lineage(result):
                raise ValueError("KPI Result lineage_id is required.")
            results.append(result)
        return results

    def _resolve_risk_results(self, context, request):
        results = []
        for result_id in request.source_risk_result_ids:
            result = self.risk_repository.get_result(context, result_id)
            self.require_entity(
                context,
                result,
                "risk_assessment_result",
                result_id,
            )
            if result.tenant_id != context.tenant_id:
                raise PermissionError("Risk Result tenant mismatch.")
            if result.status != RiskAssessmentStatus.SUCCESS:
                raise ValueError("Risk Result must be successful.")
            if not result.lineage_id:
                raise ValueError("Risk Result lineage_id is required.")
            if (
                result.period_start < request.assessment_period_start
                or result.period_end > request.assessment_period_end
                or result.entity_type != request.entity_type
                or result.entity_id != request.entity_id
            ):
                raise ValueError(
                    "Risk Result scope does not match impact assessment."
                )
            results.append(result)
        return results

    def _validate_period_and_entity(self, result, request):
        if (
            result.period_start < request.assessment_period_start
            or result.period_end > request.assessment_period_end
        ):
            raise ValueError(
                "KPI Result is outside the impact assessment period."
            )
        scoped_entity = (
            result.scope.get("entity_id")
            or result.scope.get("agent_id")
            or result.scope.get("employee_id")
        )
        if scoped_entity and str(scoped_entity) != request.entity_id:
            raise ValueError("KPI Result entity scope mismatch.")

    def _governed_factor_value(self, factor, kpi_results, risk_results):
        source_type, source_id = factor.source_reference.split(":", 1)
        if source_type == "kpi":
            matches = [
                result
                for result in kpi_results
                if result.kpi_id == source_id
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Factor {factor.impact_factor_id} requires exactly one "
                    f"governed KPI Result for {source_id}."
                )
            return matches[0].value
        matches = [
            result
            for result in risk_results
            if result.risk_definition_id == source_id
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Factor {factor.impact_factor_id} requires exactly one "
                f"governed Risk Result for {source_id}."
            )
        return matches[0].risk_score

    def _source_lineage(self, result):
        value = result.metadata.get("lineage_id")
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)] if str(value or "").strip() else []

    def _lineage(
        self,
        context,
        definition,
        factors,
        kpi_results,
        risk_results,
    ):
        upstream = []
        for result in kpi_results:
            upstream.extend(self._source_lineage(result))
        upstream.extend(
            result.lineage_id
            for result in risk_results
            if result.lineage_id
        )
        if not upstream:
            raise ValueError("lineage_id is required for persistence.")
        parts = [
            context.tenant_id,
            definition.impact_definition_id,
            definition.impact_definition_version,
            *sorted(
                f"{factor.impact_factor_id}:"
                f"{factor.impact_factor_version}:"
                f"{factor.threshold_version}:"
                f"{factor.weight}"
                for factor in factors
            ),
            *sorted(result.result_id for result in kpi_results),
            *sorted(result.result_id for result in risk_results),
            *sorted(set(upstream)),
        ]
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return f"impact:{digest}"
