from typing import Any

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.operational_source import (
    OperationalSourceRecord,
    OperationalSourceType,
    SourceQualityStatus,
    SourceValidationStatus,
)


class KPISourceEligibilityError(ValueError):
    pass


class KPISourceEligibilityService:
    def __init__(
        self,
        registry_repository,
        source_repository=None,
        audit_service=None,
        rbac_service: RBACService | None = None
    ):
        self.registry_repository = registry_repository
        self.source_repository = source_repository
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def confirm_source_eligibility(
        self,
        context: TenantContext | None,
        source_records: list[OperationalSourceRecord] | None = None,
        source_record_ids: list[str] | None = None,
        source_references: list[str] | None = None
    ) -> dict[str, Any]:
        context = require_tenant_context(context)

        if not self.rbac_service.can(context, KPIPermission.CALCULATE_KPI):
            self._audit_access_denied(
                context,
                reason="User is not allowed to use sources for KPI calculation."
            )
            self.rbac_service.require_permission(
                context,
                KPIPermission.CALCULATE_KPI
            )

        records = self._resolve_source_records(
            context,
            source_records or [],
            source_record_ids or [],
            source_references or []
        )

        for source_record in records:
            self._validate_record(
                context,
                source_record
            )

        summary = self._summary(records)
        self._audit_source_used(
            context,
            summary
        )

        return summary

    def _resolve_source_records(
        self,
        context: TenantContext,
        source_records: list[OperationalSourceRecord],
        source_record_ids: list[str],
        source_references: list[str]
    ) -> list[OperationalSourceRecord]:
        records = list(source_records)

        if source_record_ids or source_references:
            if self.source_repository is None:
                raise KPISourceEligibilityError(
                    "Source repository is required to resolve source identifiers."
                )

        for source_record_id in source_record_ids:
            record = self.source_repository.get_record(
                context,
                source_record_id
            )

            if record is None:
                raise KPISourceEligibilityError(
                    f"Source record not found: {source_record_id}"
                )

            records.append(record)

        for source_reference in source_references:
            matched_records = self.source_repository.get_records_by_source_reference(
                context,
                source_reference
            )

            if not matched_records:
                raise KPISourceEligibilityError(
                    f"Source reference not found: {source_reference}"
                )

            records.extend(matched_records)

        return self._dedupe_records(records)

    def _validate_record(
        self,
        context: TenantContext,
        source_record: OperationalSourceRecord
    ) -> None:
        if context.tenant_id != source_record.tenant_id:
            self._audit_access_denied(
                context,
                source_record,
                "Source tenant does not match context."
            )
            raise PermissionError("Source tenant does not match context.")

        if not str(source_record.lineage_id).strip():
            raise KPISourceEligibilityError("Source lineage is required.")

        if not str(source_record.source_version).strip():
            raise KPISourceEligibilityError("Source version is required.")

        registry_entry = self.registry_repository.get_entry(
            context,
            source_record.source_type
        )

        if registry_entry is None:
            raise KPISourceEligibilityError(
                f"Unsupported source type: {source_record.source_type.value}"
            )

        if not registry_entry.is_active:
            raise KPISourceEligibilityError(
                f"Inactive source type: {source_record.source_type.value}"
            )

        if source_record.validation_status == SourceValidationStatus.INVALID:
            raise KPISourceEligibilityError(
                f"Source validation failed: {source_record.validation_status.value}"
            )

        if source_record.data_quality_status != SourceQualityStatus.VALID:
            raise KPISourceEligibilityError(
                f"Source quality is not eligible: "
                f"{source_record.data_quality_status.value}"
            )

        if source_record.validation_status != SourceValidationStatus.VALID:
            raise KPISourceEligibilityError(
                f"Source validation failed: {source_record.validation_status.value}"
            )

    def _summary(
        self,
        records: list[OperationalSourceRecord]
    ) -> dict[str, Any]:
        return {
            "source_record_ids": [
                record.source_record_id
                for record in records
            ],
            "source_references": _unique_sorted(
                record.source_reference
                for record in records
                if record.source_reference
            ),
            "source_types": _unique_sorted(
                record.source_type.value
                for record in records
            ),
            "source_version": _unique_sorted(
                record.source_version
                for record in records
                if record.source_version
            ),
            "lineage_id": _unique_sorted(
                record.lineage_id
                for record in records
                if record.lineage_id
            ),
            "source_validation_status": _unique_sorted(
                record.validation_status.value
                for record in records
            ),
            "source_quality_summary": self._quality_summary(records),
        }

    def _quality_summary(
        self,
        records: list[OperationalSourceRecord]
    ) -> dict[str, int]:
        summary: dict[str, int] = {}

        for record in records:
            status = record.data_quality_status.value
            summary[status] = summary.get(status, 0) + 1

        return summary

    def _dedupe_records(
        self,
        records: list[OperationalSourceRecord]
    ) -> list[OperationalSourceRecord]:
        seen = set()
        deduped = []

        for record in records:
            if record.source_record_id in seen:
                continue

            seen.add(record.source_record_id)
            deduped.append(record)

        return deduped

    def _audit_source_used(
        self,
        context: TenantContext,
        summary: dict[str, Any]
    ) -> None:
        if self.audit_service is None or not summary["source_record_ids"]:
            return

        self.audit_service.record(
            context,
            action="SOURCE_USED_FOR_CALCULATION",
            entity_type="operational_source",
            entity_id=",".join(summary["source_record_ids"]),
            metadata={
                "source_record_ids": summary["source_record_ids"],
                "source_references": summary["source_references"],
                "source_types": summary["source_types"],
            },
        )

    def _audit_access_denied(
        self,
        context: TenantContext,
        source_record: OperationalSourceRecord | None = None,
        reason: str = ""
    ) -> None:
        if self.audit_service is None:
            return

        self.audit_service.record(
            context,
            action="SOURCE_ACCESS_DENIED",
            entity_type="operational_source",
            entity_id=(
                source_record.source_record_id
                if source_record is not None
                else "unknown"
            ),
            metadata={
                "source_type": (
                    source_record.source_type.value
                    if source_record is not None
                    else ""
                ),
                "reason": reason,
            },
        )


def _unique_sorted(values) -> list[str]:
    return sorted({
        str(value)
        for value in values
        if str(value).strip()
    })
