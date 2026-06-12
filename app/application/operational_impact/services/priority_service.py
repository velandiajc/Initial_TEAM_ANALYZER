import hashlib

from app.application.operational_impact.services._service import (
    OperationalImpactServiceSupport,
)
from app.core.permissions import OperationalImpactPermission
from app.domain.operational_impact import (
    OperationalImpactAuditEvent,
    RiskPriorityAssessment,
)
from app.domain.operational_impact.entities import new_id
from app.domain.operational_impact.rules import classify_priority
from app.models.risk import RiskAssessmentStatus


class RiskPriorityService(OperationalImpactServiceSupport):
    def __init__(
        self,
        priority_repository,
        impact_repository,
        risk_repository,
        audit_service,
        timeline_service=None,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.priority_repository = priority_repository
        self.impact_repository = impact_repository
        self.risk_repository = risk_repository
        self.timeline_service = timeline_service

    def calculate_priority(
        self,
        context,
        risk_result_id,
        impact_assessment_id,
        priority_assessment_id=None,
    ):
        context = self.context(context)
        try:
            self.require_permission(
                context,
                OperationalImpactPermission.CALCULATE_RISK_PRIORITY,
                "risk_priority_assessment",
                priority_assessment_id or "new",
                OperationalImpactAuditEvent.RISK_PRIORITY_ACCESS_DENIED,
            )
            risk = self.risk_repository.get_result(
                context,
                risk_result_id,
            )
            impact = self.impact_repository.get_by_id(
                context,
                impact_assessment_id,
            )
            self.require_entity(
                context,
                risk,
                "risk_assessment_result",
                risk_result_id,
                OperationalImpactAuditEvent.RISK_PRIORITY_ACCESS_DENIED,
            )
            self.require_entity(
                context,
                impact,
                "operational_impact_assessment",
                impact_assessment_id,
                OperationalImpactAuditEvent.RISK_PRIORITY_ACCESS_DENIED,
            )
            if (
                risk.tenant_id != context.tenant_id
                or impact.tenant_id != context.tenant_id
            ):
                raise PermissionError("Priority inputs must be tenant-scoped.")
            if risk.status != RiskAssessmentStatus.SUCCESS:
                raise ValueError("Risk Result must be successful.")
            if (
                risk.entity_type != impact.entity_type
                or risk.entity_id != impact.entity_id
            ):
                raise ValueError("Risk and Impact entity scope must match.")
            for value, name in (
                (risk.lineage_id, "lineage_id"),
                (
                    risk.risk_definition_version,
                    "risk_definition_version",
                ),
                (risk.rule_version_number, "risk_rule_version"),
                (
                    impact.impact_definition_version,
                    "impact_definition_version",
                ),
            ):
                if not str(value).strip():
                    raise ValueError(f"{name} is required.")

            previous_items = self.priority_repository.list_for_entity(
                context,
                impact.entity_type,
                impact.entity_id,
            )
            previous_priority = previous_items[-1] if previous_items else None
            previous_impact = (
                self.impact_repository.get_by_id(
                    context,
                    previous_priority.impact_assessment_id,
                )
                if previous_priority
                else None
            )
            priority_score = round(
                float(risk.risk_score) * impact.impact_score / 100,
                4,
            )
            priority_level = classify_priority(priority_score)
            lineage_id = self._lineage(risk, impact)
            priority = RiskPriorityAssessment(
                priority_assessment_id=priority_assessment_id or new_id(),
                tenant_id=context.tenant_id,
                risk_result_id=risk.result_id,
                risk_definition_version=risk.risk_definition_version,
                risk_rule_version=risk.rule_version_number,
                impact_assessment_id=impact.impact_assessment_id,
                impact_definition_version=impact.impact_definition_version,
                entity_type=impact.entity_type,
                entity_id=impact.entity_id,
                risk_score_snapshot=risk.risk_score,
                impact_score_snapshot=impact.impact_score,
                priority_score=priority_score,
                priority_level=priority_level,
                priority_reason=(
                    f"Risk score {risk.risk_score} combined with "
                    f"Operational Impact score {impact.impact_score}."
                ),
                lineage_id=lineage_id,
                created_by=context.user_id,
            )
            self.priority_repository.save(context, priority)
            if self.timeline_service:
                self.timeline_service.create_if_material(
                    context,
                    previous_impact,
                    previous_priority,
                    impact,
                    priority,
                )
            self.audit(
                context,
                OperationalImpactAuditEvent.RISK_PRIORITY_CALCULATED,
                "risk_priority_assessment",
                priority.priority_assessment_id,
                {
                    "risk_result_id": priority.risk_result_id,
                    "impact_assessment_id": (
                        priority.impact_assessment_id
                    ),
                    "risk_definition_version": (
                        priority.risk_definition_version
                    ),
                    "risk_rule_version": priority.risk_rule_version,
                    "impact_definition_version": (
                        priority.impact_definition_version
                    ),
                    "risk_score_snapshot": (
                        priority.risk_score_snapshot
                    ),
                    "impact_score_snapshot": (
                        priority.impact_score_snapshot
                    ),
                    "priority_score": priority.priority_score,
                    "priority_level": priority.priority_level.value,
                    "lineage_id": priority.lineage_id,
                },
            )
            return priority
        except PermissionError:
            raise
        except ValueError as exc:
            self.audit(
                context,
                OperationalImpactAuditEvent.RISK_PRIORITY_REJECTED,
                "risk_priority_assessment",
                priority_assessment_id or "new",
                {"reason": str(exc)},
            )
            raise
        except Exception as exc:
            self.audit(
                context,
                OperationalImpactAuditEvent.RISK_PRIORITY_CALCULATION_FAILED,
                "risk_priority_assessment",
                priority_assessment_id or "new",
                {"reason": str(exc)},
            )
            raise

    def get_priority(self, context, assessment_id):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.VIEW_RISK_PRIORITY,
            "risk_priority_assessment",
            assessment_id,
            OperationalImpactAuditEvent.RISK_PRIORITY_ACCESS_DENIED,
        )
        assessment = self.priority_repository.get_by_id(
            context,
            assessment_id,
        )
        self.require_entity(
            context,
            assessment,
            "risk_priority_assessment",
            assessment_id,
            OperationalImpactAuditEvent.RISK_PRIORITY_ACCESS_DENIED,
        )
        self.audit(
            context,
            OperationalImpactAuditEvent.RISK_PRIORITY_VIEWED,
            "risk_priority_assessment",
            assessment_id,
            {"priority_level": assessment.priority_level.value},
        )
        return assessment

    def _lineage(self, risk, impact):
        parts = [
            risk.lineage_id,
            risk.result_id,
            risk.risk_definition_version,
            risk.rule_version_number,
            impact.lineage_id,
            impact.impact_assessment_id,
            impact.impact_definition_version,
        ]
        if any(not str(value).strip() for value in parts):
            raise ValueError("Priority lineage references are incomplete.")
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return f"priority:{digest}"
