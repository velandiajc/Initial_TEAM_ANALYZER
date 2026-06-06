from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.operational_source import (
    OperationalSourceType,
    SourceRegistryEntry,
)


class SourceRegistryService:
    def __init__(
        self,
        registry_repository,
        audit_service,
        rbac_service: RBACService | None = None
    ):
        self.registry_repository = registry_repository
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def register_source_type(
        self,
        context: TenantContext | None,
        registry_entry: SourceRegistryEntry
    ) -> SourceRegistryEntry:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.REGISTER_SOURCE_TYPE
        )

        if context.tenant_id != registry_entry.tenant_id:
            raise PermissionError("Source registry tenant does not match context.")

        registry_entry.source_type = OperationalSourceType.from_value(
            registry_entry.source_type
        )
        _require_text(registry_entry.source_owner, "source_owner")
        _require_text(registry_entry.source_steward, "source_steward")

        existing = self.registry_repository.get_entry(
            context,
            registry_entry.source_type
        )

        if existing is not None and existing.is_active and registry_entry.is_active:
            raise ValueError(
                f"Active source type already registered: "
                f"{registry_entry.source_type.value}"
            )

        self.registry_repository.upsert_entry(
            context,
            registry_entry
        )
        self.audit_service.record(
            context,
            action="SOURCE_REGISTERED",
            entity_type="operational_source_type",
            entity_id=registry_entry.source_type.value,
            metadata={
                "source_type": registry_entry.source_type.value,
                "source_owner": registry_entry.source_owner,
                "source_steward": registry_entry.source_steward,
                "is_active": registry_entry.is_active,
            },
        )

        return registry_entry

    def get_source_type(
        self,
        context: TenantContext | None,
        source_type: OperationalSourceType | str
    ) -> SourceRegistryEntry | None:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.VIEW_OPERATIONAL_SOURCE
        )
        source_type = OperationalSourceType.from_value(source_type)

        return self.registry_repository.get_entry(
            context,
            source_type
        )

    def require_active_source_type(
        self,
        context: TenantContext | None,
        source_type: OperationalSourceType | str
    ) -> SourceRegistryEntry:
        context = require_tenant_context(context)
        entry = self.get_source_type(
            context,
            source_type
        )

        if entry is None:
            raise ValueError(f"Unsupported source type: {source_type}")

        if not entry.is_active:
            raise ValueError(f"Source type is inactive: {entry.source_type.value}")

        return entry

    def list_source_types(
        self,
        context: TenantContext | None
    ) -> list[SourceRegistryEntry]:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.VIEW_OPERATIONAL_SOURCE
        )

        return self.registry_repository.list_entries(context)


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required.")
