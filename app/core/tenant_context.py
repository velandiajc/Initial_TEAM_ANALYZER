from dataclasses import dataclass, field


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str
    roles: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not str(self.tenant_id).strip():
            raise ValueError("tenant_id is required.")

        if not str(self.user_id).strip():
            raise ValueError("user_id is required.")

        normalized_roles = {
            self._role_value(role)
            for role in self.roles
            if self._role_value(role)
        }

        object.__setattr__(self, "roles", normalized_roles)

    def has_role(self, role: str) -> bool:
        return self._role_value(role) in self.roles

    def require(self) -> "TenantContext":
        return self

    def _role_value(self, role) -> str:
        value = getattr(role, "value", role)
        return str(value).strip().lower()


def require_tenant_context(context: TenantContext | None) -> TenantContext:
    if context is None:
        raise ValueError("TenantContext required.")

    return context.require()
