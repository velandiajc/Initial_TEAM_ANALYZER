from datetime import date, datetime

from app.core.tenant_context import TenantContext, require_tenant_context


def scoped_context(context: TenantContext | None) -> TenantContext:
    return require_tenant_context(context)


def require_same_tenant(context: TenantContext, tenant_id: str) -> None:
    if context.tenant_id != tenant_id:
        raise PermissionError("Repository access must be tenant-scoped.")


def datetime_text(value: datetime) -> str:
    return value.isoformat()


def date_text(value: date) -> str:
    return value.isoformat()


def text_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def text_date(value: str) -> date:
    return date.fromisoformat(value)


def require_persistence_lineage(
    lineage_id: str,
    evidence_pack_id: str | None = None,
    risk_result_id: str | None = None,
) -> None:
    if not str(lineage_id).strip():
        raise ValueError("lineage_id is required for persistence.")
    if evidence_pack_id is not None and not str(evidence_pack_id).strip():
        raise ValueError("evidence_pack_id is required for persistence.")
    if risk_result_id is not None and not str(risk_result_id).strip():
        raise ValueError("risk_result_id is required for persistence.")
