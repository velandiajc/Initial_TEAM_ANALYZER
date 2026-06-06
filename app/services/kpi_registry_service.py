from uuid import uuid4

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import (
    FormulaStatus,
    FormulaVersion,
    KPIDefinition,
    KPIDomain,
    KPILifecycle,
    KPIThreshold,
)


class KPIRegistryService:
    def __init__(
        self,
        definition_repository,
        audit_service,
        rbac_service: RBACService | None = None
    ):
        self.definition_repository = definition_repository
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def register_kpi(
        self,
        context: TenantContext | None,
        kpi_id: str,
        name: str,
        domain: KPIDomain | str,
        owner_user_id: str,
        steward_user_id: str,
        description: str = ""
    ) -> KPIDefinition:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.REGISTER_KPI
        )

        definition = KPIDefinition(
            kpi_id=kpi_id,
            tenant_id=context.tenant_id,
            name=name,
            description=description,
            domain=KPIDomain.from_value(domain),
            owner_user_id=owner_user_id,
            steward_user_id=steward_user_id,
            created_by=context.user_id,
        )

        self.definition_repository.upsert_definition(
            context,
            definition
        )
        self.audit_service.record(
            context,
            action="kpi_definition_registered",
            entity_type="kpi_definition",
            entity_id=definition.kpi_id,
            metadata={
                "domain": definition.domain.value,
                "owner_user_id": definition.owner_user_id,
                "steward_user_id": definition.steward_user_id,
            },
        )

        return definition

    def update_ownership(
        self,
        context: TenantContext | None,
        kpi_id: str,
        owner_user_id: str,
        steward_user_id: str
    ) -> KPIDefinition:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.UPDATE_OWNERSHIP
        )
        _require_text(owner_user_id, "owner_user_id")
        _require_text(steward_user_id, "steward_user_id")
        definition = self._require_definition(context, kpi_id)
        definition.owner_user_id = owner_user_id
        definition.steward_user_id = steward_user_id
        definition.move_to_lifecycle(definition.lifecycle)

        self.definition_repository.upsert_definition(
            context,
            definition
        )
        self.audit_service.record(
            context,
            action="kpi_ownership_updated",
            entity_type="kpi_definition",
            entity_id=kpi_id,
            metadata={
                "owner_user_id": owner_user_id,
                "steward_user_id": steward_user_id,
            },
        )

        return definition

    def add_threshold(
        self,
        context: TenantContext | None,
        kpi_id: str,
        name: str,
        risk_level: str,
        target: float | None = None,
        minimum: float | None = None,
        maximum: float | None = None,
        threshold_id: str | None = None
    ) -> KPIThreshold:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.WRITE_THRESHOLD
        )
        self._require_definition(context, kpi_id)

        threshold = KPIThreshold(
            threshold_id=threshold_id or str(uuid4()),
            tenant_id=context.tenant_id,
            kpi_id=kpi_id,
            name=name,
            risk_level=risk_level,
            target=target,
            minimum=minimum,
            maximum=maximum,
            created_by=context.user_id,
        )

        self.definition_repository.upsert_threshold(
            context,
            threshold
        )
        self.audit_service.record(
            context,
            action="kpi_threshold_added",
            entity_type="kpi_threshold",
            entity_id=threshold.threshold_id,
            metadata={
                "kpi_id": kpi_id,
                "risk_level": risk_level,
            },
        )

        return threshold

    def submit_formula_version(
        self,
        context: TenantContext | None,
        kpi_id: str,
        version: str,
        expression: str,
        notes: str = "",
        formula_version_id: str | None = None
    ) -> FormulaVersion:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.SUBMIT_FORMULA
        )
        self._require_definition(context, kpi_id)
        formula_version = FormulaVersion(
            formula_version_id=formula_version_id or str(uuid4()),
            tenant_id=context.tenant_id,
            kpi_id=kpi_id,
            version=version,
            expression=expression,
            created_by=context.user_id,
            status=FormulaStatus.PENDING_APPROVAL,
            notes=notes,
        )

        self.definition_repository.upsert_formula_version(
            context,
            formula_version
        )
        self.audit_service.record(
            context,
            action="formula_version_submitted",
            entity_type="formula_version",
            entity_id=formula_version.formula_version_id,
            metadata={
                "kpi_id": kpi_id,
                "version": version,
                "status": formula_version.status.value,
            },
        )

        return formula_version

    def approve_formula_version(
        self,
        context: TenantContext | None,
        formula_version_id: str
    ) -> FormulaVersion:
        context = require_tenant_context(context)
        formula_version = self.definition_repository.get_formula_version(
            context,
            formula_version_id
        )

        if formula_version is None:
            raise ValueError(
                f"Formula version not found: {formula_version_id}"
            )

        if formula_version.status != FormulaStatus.PENDING_APPROVAL:
            raise ValueError("Only pending formula versions can be approved.")

        self.rbac_service.require_formula_approval(
            context,
            formula_version
        )
        formula_version.approve(context.user_id)
        self.definition_repository.upsert_formula_version(
            context,
            formula_version
        )
        self.audit_service.record(
            context,
            action="formula_version_approved",
            entity_type="formula_version",
            entity_id=formula_version.formula_version_id,
            metadata={
                "kpi_id": formula_version.kpi_id,
                "version": formula_version.version,
                "approved_by": context.user_id,
            },
        )

        return formula_version

    def change_lifecycle(
        self,
        context: TenantContext | None,
        kpi_id: str,
        lifecycle: KPILifecycle | str
    ) -> KPIDefinition:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.CHANGE_LIFECYCLE
        )
        lifecycle = KPILifecycle.from_value(lifecycle)
        definition = self.definition_repository.update_lifecycle(
            context,
            kpi_id,
            lifecycle
        )
        self.audit_service.record(
            context,
            action="kpi_lifecycle_changed",
            entity_type="kpi_definition",
            entity_id=kpi_id,
            metadata={
                "lifecycle": lifecycle.value,
            },
        )

        return definition

    def get_kpi(
        self,
        context: TenantContext | None,
        kpi_id: str
    ) -> KPIDefinition | None:
        context = require_tenant_context(context)

        return self.definition_repository.get_definition(
            context,
            kpi_id
        )

    def list_kpis(
        self,
        context: TenantContext | None
    ) -> list[KPIDefinition]:
        context = require_tenant_context(context)

        return self.definition_repository.list_definitions(context)

    def _require_definition(
        self,
        context: TenantContext,
        kpi_id: str
    ) -> KPIDefinition:
        definition = self.definition_repository.get_definition(
            context,
            kpi_id
        )

        if definition is None:
            raise ValueError(f"KPI definition not found: {kpi_id}")

        return definition


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")


class FormulaGovernanceService:
    def __init__(self, registry_service: KPIRegistryService):
        self.registry_service = registry_service

    def submit_formula_version(
        self,
        context: TenantContext | None,
        kpi_id: str,
        version: str,
        expression: str,
        notes: str = "",
        formula_version_id: str | None = None
    ) -> FormulaVersion:
        return self.registry_service.submit_formula_version(
            context,
            kpi_id=kpi_id,
            version=version,
            expression=expression,
            notes=notes,
            formula_version_id=formula_version_id,
        )

    def approve_formula_version(
        self,
        context: TenantContext | None,
        formula_version_id: str
    ) -> FormulaVersion:
        return self.registry_service.approve_formula_version(
            context,
            formula_version_id
        )


class OwnershipService:
    def __init__(self, registry_service: KPIRegistryService):
        self.registry_service = registry_service

    def update_ownership(
        self,
        context: TenantContext | None,
        kpi_id: str,
        owner_user_id: str,
        steward_user_id: str
    ) -> KPIDefinition:
        return self.registry_service.update_ownership(
            context,
            kpi_id=kpi_id,
            owner_user_id=owner_user_id,
            steward_user_id=steward_user_id,
        )


class LifecycleService:
    def __init__(self, registry_service: KPIRegistryService):
        self.registry_service = registry_service

    def change_lifecycle(
        self,
        context: TenantContext | None,
        kpi_id: str,
        lifecycle: KPILifecycle | str
    ) -> KPIDefinition:
        return self.registry_service.change_lifecycle(
            context,
            kpi_id=kpi_id,
            lifecycle=lifecycle,
        )
