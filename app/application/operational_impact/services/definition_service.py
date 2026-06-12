from app.application.operational_impact.services._service import (
    OperationalImpactServiceSupport,
)
from app.core.permissions import OperationalImpactPermission
from app.domain.operational_impact import (
    ImpactGovernanceStatus,
    OperationalImpactAuditEvent,
    OperationalImpactDefinition,
)


class OperationalImpactDefinitionService(OperationalImpactServiceSupport):
    def __init__(self, definition_repository, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.definition_repository = definition_repository

    def create_definition(
        self,
        context,
        impact_definition_id,
        name,
        description,
        impact_category,
        owner,
        steward,
        impact_definition_version,
        effective_date,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.CREATE_OPERATIONAL_IMPACT_DEFINITION,
            "operational_impact_definition",
            impact_definition_id,
        )
        if self.definition_repository.get_version(
            context,
            impact_definition_id,
            impact_definition_version,
        ):
            raise ValueError("Operational Impact definition version exists.")
        definition = OperationalImpactDefinition(
            impact_definition_id=impact_definition_id,
            tenant_id=context.tenant_id,
            name=name,
            description=description,
            impact_category=impact_category,
            owner=owner,
            steward=steward,
            status=ImpactGovernanceStatus.DRAFT,
            impact_definition_version=impact_definition_version,
            effective_date=effective_date,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.definition_repository.save(context, definition)
        self.audit(
            context,
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_DEFINITION_CREATED,
            "operational_impact_definition",
            definition.impact_definition_id,
            {
                "impact_definition_version": impact_definition_version,
                "impact_category": impact_category,
                "owner": owner,
                "steward": steward,
            },
        )
        return definition

    def approve_definition(self, context, definition_id, version):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.APPROVE_OPERATIONAL_IMPACT_DEFINITION,
            "operational_impact_definition",
            definition_id,
        )
        definition = self.require_entity(
            context,
            self.definition_repository.get_version(
                context,
                definition_id,
                version,
            ),
            "operational_impact_definition",
            definition_id,
        )
        approved = definition.approve(context.user_id)
        self.definition_repository.save(context, approved)
        self.audit(
            context,
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_DEFINITION_APPROVED,
            "operational_impact_definition",
            definition_id,
            {
                "impact_definition_version": version,
                "approved_by": context.user_id,
            },
        )
        return approved

    def activate_definition(self, context, definition_id, version):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.APPROVE_OPERATIONAL_IMPACT_DEFINITION,
            "operational_impact_definition",
            definition_id,
        )
        definition = self.require_entity(
            context,
            self.definition_repository.get_version(
                context,
                definition_id,
                version,
            ),
            "operational_impact_definition",
            definition_id,
        )
        active = definition.activate(context.user_id)
        self.definition_repository.deactivate_other_versions(context, active)
        self.definition_repository.save(context, active)
        return active

    def get_active_definition(self, context, definition_id):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.VIEW_OPERATIONAL_IMPACT,
            "operational_impact_definition",
            definition_id,
        )
        return self.require_entity(
            context,
            self.definition_repository.get_active(context, definition_id),
            "operational_impact_definition",
            definition_id,
        )
