from datetime import datetime
from uuid import uuid4

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.risk import (
    RiskDefinition,
    RiskDefinitionLifecycle,
    RiskRuleStatus,
    RiskRuleVersion,
)
from app.services.risk_rule_version_service import RiskRuleVersionService


class RiskRegistryService:
    def __init__(
        self,
        risk_repository,
        audit_service,
        rbac_service: RBACService | None = None,
        rule_version_service: RiskRuleVersionService | None = None
    ):
        self.risk_repository = risk_repository
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()
        self.rule_version_service = (
            rule_version_service
            or RiskRuleVersionService(risk_repository)
        )

    def register_risk_definition(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        name: str,
        category: str,
        owner_user_id: str,
        steward_user_id: str,
        description: str = "",
        metadata: dict | None = None
    ) -> RiskDefinition:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.MANAGE_RISK_DEFINITIONS
        )

        definition = RiskDefinition(
            risk_definition_id=risk_definition_id,
            tenant_id=context.tenant_id,
            name=name,
            description=description,
            category=category,
            owner_user_id=owner_user_id,
            steward_user_id=steward_user_id,
            created_by=context.user_id,
            metadata=metadata or {},
        )

        self.risk_repository.upsert_definition(context, definition)
        self.audit_service.record(
            context,
            action="risk_definition_registered",
            entity_type="risk_definition",
            entity_id=definition.risk_definition_id,
            metadata={
                "category": definition.category,
                "owner_user_id": definition.owner_user_id,
                "steward_user_id": definition.steward_user_id,
            },
        )

        return definition

    def update_ownership(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        owner_user_id: str,
        steward_user_id: str
    ) -> RiskDefinition:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.MANAGE_RISK_DEFINITIONS
        )
        _require_text(owner_user_id, "owner_user_id")
        _require_text(steward_user_id, "steward_user_id")
        definition = self._require_definition(context, risk_definition_id)
        definition.owner_user_id = owner_user_id
        definition.steward_user_id = steward_user_id
        definition.move_to_lifecycle(definition.lifecycle)

        self.risk_repository.upsert_definition(context, definition)
        self.audit_service.record(
            context,
            action="risk_ownership_updated",
            entity_type="risk_definition",
            entity_id=risk_definition_id,
            metadata={
                "owner_user_id": owner_user_id,
                "steward_user_id": steward_user_id,
            },
        )

        return definition

    def submit_rule_version(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        version: str,
        handler_key: str,
        parameters: dict,
        notes: str = "",
        rule_version_id: str | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        supersedes_rule_version_id: str | None = None
    ) -> RiskRuleVersion:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.MANAGE_RISK_RULES
        )
        self._require_definition(context, risk_definition_id)

        rule_version = RiskRuleVersion(
            rule_version_id=rule_version_id or str(uuid4()),
            tenant_id=context.tenant_id,
            risk_definition_id=risk_definition_id,
            version=version,
            handler_key=handler_key,
            parameters=parameters,
            created_by=context.user_id,
            status=RiskRuleStatus.REVIEW,
            effective_from=effective_from,
            effective_to=effective_to,
            supersedes_rule_version_id=supersedes_rule_version_id,
            notes=notes,
        )

        self.risk_repository.upsert_rule_version(context, rule_version)
        self.audit_service.record(
            context,
            action="risk_rule_version_submitted",
            entity_type="risk_rule_version",
            entity_id=rule_version.rule_version_id,
            metadata={
                "risk_definition_id": risk_definition_id,
                "version": version,
                "handler_key": handler_key,
                "status": rule_version.status.value,
            },
        )

        return rule_version

    def approve_rule_version(
        self,
        context: TenantContext | None,
        rule_version_id: str
    ) -> RiskRuleVersion:
        context = require_tenant_context(context)
        rule_version = self.risk_repository.get_rule_version(
            context,
            rule_version_id
        )

        if rule_version is None:
            raise ValueError(f"Risk rule version not found: {rule_version_id}")

        if rule_version.status != RiskRuleStatus.REVIEW:
            raise ValueError("Only review risk rule versions can be approved.")

        self.rbac_service.require_risk_rule_approval(context, rule_version)
        rule_version.approve(context.user_id)
        self.risk_repository.upsert_rule_version(context, rule_version)
        self.audit_service.record(
            context,
            action="risk_rule_version_approved",
            entity_type="risk_rule_version",
            entity_id=rule_version.rule_version_id,
            metadata={
                "risk_definition_id": rule_version.risk_definition_id,
                "version": rule_version.version,
                "approved_by": context.user_id,
            },
        )

        return rule_version

    def activate_rule_version(
        self,
        context: TenantContext | None,
        rule_version_id: str
    ) -> RiskRuleVersion:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.MANAGE_RISK_RULES
        )
        rule_version = self.risk_repository.get_rule_version(
            context,
            rule_version_id
        )

        if rule_version is None:
            raise ValueError(f"Risk rule version not found: {rule_version_id}")

        rule_version.activate()
        self.rule_version_service.validate_no_active_period_conflict(
            context,
            rule_version
        )
        self.risk_repository.upsert_rule_version(context, rule_version)
        self.audit_service.record(
            context,
            action="risk_rule_version_activated",
            entity_type="risk_rule_version",
            entity_id=rule_version.rule_version_id,
            metadata={
                "risk_definition_id": rule_version.risk_definition_id,
                "version": rule_version.version,
            },
        )

        return rule_version

    def change_lifecycle(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        lifecycle: RiskDefinitionLifecycle | str
    ) -> RiskDefinition:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.MANAGE_RISK_DEFINITIONS
        )
        lifecycle = RiskDefinitionLifecycle.from_value(lifecycle)
        definition = self.risk_repository.update_lifecycle(
            context,
            risk_definition_id,
            lifecycle
        )
        self.audit_service.record(
            context,
            action="risk_definition_lifecycle_changed",
            entity_type="risk_definition",
            entity_id=risk_definition_id,
            metadata={
                "lifecycle": lifecycle.value,
            },
        )

        return definition

    def get_definition(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> RiskDefinition | None:
        context = require_tenant_context(context)

        return self.risk_repository.get_definition(
            context,
            risk_definition_id
        )

    def list_definitions(
        self,
        context: TenantContext | None
    ) -> list[RiskDefinition]:
        context = require_tenant_context(context)

        return self.risk_repository.list_definitions(context)

    def _require_definition(
        self,
        context: TenantContext,
        risk_definition_id: str
    ) -> RiskDefinition:
        definition = self.risk_repository.get_definition(
            context,
            risk_definition_id
        )

        if definition is None:
            raise ValueError(
                f"Risk definition not found: {risk_definition_id}"
            )

        return definition


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")
