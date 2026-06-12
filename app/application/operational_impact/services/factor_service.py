from app.application.operational_impact.services._service import (
    OperationalImpactServiceSupport,
)
from app.core.permissions import OperationalImpactPermission
from app.domain.operational_impact import (
    ImpactDirection,
    ImpactGovernanceStatus,
    OperationalImpactAuditEvent,
    OperationalImpactFactor,
)


APPROVED_MVP_FACTOR_NAMES = {
    "survey volume",
    "handled contacts",
    "qa critical errors",
    "attendance instability",
    "adherence deviation",
    "escalation frequency",
    "unresolved coaching commitments",
    "repeated kpi failure",
}


class OperationalImpactFactorService(OperationalImpactServiceSupport):
    def __init__(
        self,
        factor_repository,
        definition_repository,
        audit_service,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.factor_repository = factor_repository
        self.definition_repository = definition_repository

    def create_factor(
        self,
        context,
        impact_factor_id,
        impact_definition_id,
        impact_definition_version,
        name,
        description,
        source_reference,
        weight,
        direction,
        threshold_version,
        threshold_min,
        threshold_max,
        impact_factor_version,
        owner,
        steward,
        effective_date,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.CREATE_OPERATIONAL_IMPACT_DEFINITION,
            "operational_impact_factor",
            impact_factor_id,
        )
        if name.strip().lower() not in APPROVED_MVP_FACTOR_NAMES:
            raise ValueError("Factor is outside the approved Sprint 6 MVP set.")
        definition = self.definition_repository.get_version(
            context,
            impact_definition_id,
            impact_definition_version,
        )
        self.require_entity(
            context,
            definition,
            "operational_impact_definition",
            impact_definition_id,
        )
        if self.factor_repository.get_version(
            context,
            impact_factor_id,
            impact_factor_version,
        ):
            raise ValueError("Operational Impact factor version exists.")
        factor = OperationalImpactFactor(
            impact_factor_id=impact_factor_id,
            tenant_id=context.tenant_id,
            impact_definition_id=impact_definition_id,
            impact_definition_version=impact_definition_version,
            name=name,
            description=description,
            source_reference=source_reference,
            weight=weight,
            direction=ImpactDirection.from_value(direction),
            threshold_version=threshold_version,
            threshold_min=threshold_min,
            threshold_max=threshold_max,
            impact_factor_version=impact_factor_version,
            owner=owner,
            steward=steward,
            status=ImpactGovernanceStatus.DRAFT,
            effective_date=effective_date,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.factor_repository.save(context, factor)
        self.audit(
            context,
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_FACTOR_CREATED,
            "operational_impact_factor",
            impact_factor_id,
            {
                "impact_definition_id": impact_definition_id,
                "impact_definition_version": impact_definition_version,
                "impact_factor_version": impact_factor_version,
                "threshold_version": threshold_version,
                "weight": weight,
            },
        )
        return factor

    def approve_factor(self, context, factor_id, version):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.APPROVE_OPERATIONAL_IMPACT_DEFINITION,
            "operational_impact_factor",
            factor_id,
        )
        factor = self.require_entity(
            context,
            self.factor_repository.get_version(context, factor_id, version),
            "operational_impact_factor",
            factor_id,
        )
        approved = factor.approve(context.user_id)
        self.factor_repository.save(context, approved)
        self.audit(
            context,
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_FACTOR_APPROVED,
            "operational_impact_factor",
            factor_id,
            {
                "impact_factor_version": version,
                "approved_by": context.user_id,
            },
        )
        return approved

    def activate_factor(self, context, factor_id, version):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.APPROVE_OPERATIONAL_IMPACT_DEFINITION,
            "operational_impact_factor",
            factor_id,
        )
        factor = self.require_entity(
            context,
            self.factor_repository.get_version(context, factor_id, version),
            "operational_impact_factor",
            factor_id,
        )
        definition = self.definition_repository.get_version(
            context,
            factor.impact_definition_id,
            factor.impact_definition_version,
        )
        if (
            definition is None
            or definition.status != ImpactGovernanceStatus.ACTIVE
        ):
            raise ValueError(
                "Factor definition must be active before factor activation."
            )
        active = factor.activate(context.user_id)
        existing = self.factor_repository.list_active_for_definition(
            context,
            active.impact_definition_id,
            active.impact_definition_version,
        )
        unique_ids = {
            item.impact_factor_id
            for item in existing
            if item.impact_factor_id != active.impact_factor_id
        }
        if len(unique_ids) >= 8:
            raise ValueError("Operational Impact MVP supports at most 8 factors.")
        self.factor_repository.deactivate_other_versions(context, active)
        self.factor_repository.save(context, active)
        return active
