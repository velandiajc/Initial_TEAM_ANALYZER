from datetime import datetime, timezone
from typing import Any

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import utc_now
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceRecord,
    OperationalSourceType,
    SourceQualityDimension,
    SourceQualityStatus,
    SourceRegistryEntry,
    SourceValidationResult,
    SourceValidationStatus,
    source_quality_issue,
)


class SourceValidationService:
    def __init__(
        self,
        registry_repository,
        source_repository=None,
        validation_repository=None,
        audit_service=None,
        rbac_service: RBACService | None = None
    ):
        self.registry_repository = registry_repository
        self.source_repository = source_repository
        self.validation_repository = validation_repository
        self.audit_service = audit_service
        self.rbac_service = rbac_service or RBACService()

    def validate_source(
        self,
        context: TenantContext | None,
        source_record: OperationalSourceRecord
    ) -> SourceValidationResult:
        context = require_tenant_context(context)

        if not self.rbac_service.can(
            context,
            KPIPermission.VALIDATE_OPERATIONAL_SOURCE
        ):
            self._audit(
                context,
                action="SOURCE_VALIDATION_FAILED",
                source_record=source_record,
                status=SourceValidationStatus.INVALID.value,
                reason="Unauthorized source validation attempt.",
            )
            self.rbac_service.require_permission(
                context,
                KPIPermission.VALIDATE_OPERATIONAL_SOURCE
            )

        if context.tenant_id != source_record.tenant_id:
            result = self._result(
                context,
                source_record,
                SourceValidationStatus.INVALID,
                SourceQualityStatus.TENANT_MISMATCH,
                [
                    source_quality_issue(
                        SourceQualityDimension.CONSISTENCY,
                        SourceQualityStatus.TENANT_MISMATCH,
                        message="Source tenant does not match context.",
                    )
                ],
            )
            self._persist_validation_result(context, result)
            self._audit_result(
                context,
                "SOURCE_REJECTED",
                source_record,
                result
            )
            raise PermissionError("Source tenant does not match context.")

        try:
            registry_entry = self._get_registry_entry(
                context,
                source_record.source_type
            )
            quality_issues = self._collect_quality_issues(
                context,
                source_record,
                registry_entry
            )
            validation_status = self._validation_status(quality_issues)
            data_quality_status = self._data_quality_status(quality_issues)
            result = self._result(
                context,
                source_record,
                validation_status,
                data_quality_status,
                quality_issues,
            )

            source_record.validation_status = validation_status
            source_record.data_quality_status = data_quality_status

            if (
                self.source_repository is not None
                and validation_status != SourceValidationStatus.INVALID
            ):
                self.source_repository.save(
                    context,
                    source_record
                )

            self._persist_validation_result(context, result)
            self._audit_result(
                context,
                (
                    "SOURCE_REJECTED"
                    if validation_status == SourceValidationStatus.INVALID
                    else "SOURCE_VALIDATED"
                ),
                source_record,
                result
            )

            return result
        except Exception as exc:
            if isinstance(exc, PermissionError):
                raise

            self._audit(
                context,
                action="SOURCE_VALIDATION_FAILED",
                source_record=source_record,
                status=SourceValidationStatus.INVALID.value,
                reason=str(exc),
            )
            raise

    def _get_registry_entry(
        self,
        context: TenantContext,
        source_type: OperationalSourceType | str
    ) -> SourceRegistryEntry | None:
        try:
            source_type = OperationalSourceType.from_value(source_type)
        except ValueError:
            return None

        return self.registry_repository.get_entry(
            context,
            source_type
        )

    def _collect_quality_issues(
        self,
        context: TenantContext,
        source_record: OperationalSourceRecord,
        registry_entry: SourceRegistryEntry | None
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        if registry_entry is None:
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.VALIDITY,
                    SourceQualityStatus.UNSUPPORTED_SOURCE_TYPE,
                    message="Source type is not registered.",
                )
            )
            return issues

        if not registry_entry.is_active:
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.VALIDITY,
                    SourceQualityStatus.UNSUPPORTED_SOURCE_TYPE,
                    message="Source type is inactive.",
                )
            )

        self._validate_required_source_fields(source_record, issues)
        self._validate_period(source_record, issues)
        self._validate_entity_scope(source_record, registry_entry, issues)
        self._validate_metric_values(source_record, registry_entry, issues)
        self._validate_duplicate_source(context, source_record, issues)
        self._validate_freshness(source_record, registry_entry, issues)

        return issues

    def _validate_required_source_fields(
        self,
        source_record: OperationalSourceRecord,
        issues: list[dict[str, Any]]
    ) -> None:
        required_text_fields = {
            "source_reference": source_record.source_reference,
            "source_version": source_record.source_version,
            "lineage_id": source_record.lineage_id,
        }

        for field_name, value in required_text_fields.items():
            if not str(value).strip():
                issues.append(
                    source_quality_issue(
                        SourceQualityDimension.COMPLETENESS,
                        SourceQualityStatus.MISSING_REQUIRED_FIELD,
                        field_name=field_name,
                    )
                )

        if source_record.period_start is None:
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.COMPLETENESS,
                    SourceQualityStatus.MISSING_REQUIRED_FIELD,
                    field_name="period_start",
                )
            )

        if source_record.period_end is None:
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.COMPLETENESS,
                    SourceQualityStatus.MISSING_REQUIRED_FIELD,
                    field_name="period_end",
                )
            )

    def _validate_period(
        self,
        source_record: OperationalSourceRecord,
        issues: list[dict[str, Any]]
    ) -> None:
        if (
            source_record.period_start is not None
            and source_record.period_end is not None
            and source_record.period_start > source_record.period_end
        ):
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.VALIDITY,
                    SourceQualityStatus.INVALID_PERIOD,
                    field_name="period_start",
                    message="period_start must be before or equal to period_end.",
                )
            )

    def _validate_entity_scope(
        self,
        source_record: OperationalSourceRecord,
        registry_entry: SourceRegistryEntry,
        issues: list[dict[str, Any]]
    ) -> None:
        if (
            registry_entry.allowed_entity_scopes
            and source_record.entity_type not in registry_entry.allowed_entity_scopes
        ):
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.VALIDITY,
                    SourceQualityStatus.INVALID_ENTITY_SCOPE,
                    field_name="entity_type",
                )
            )

        if (
            source_record.entity_type != OperationalEntityScope.TENANT
            and not str(source_record.entity_id).strip()
        ):
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.COMPLETENESS,
                    SourceQualityStatus.MISSING_REQUIRED_FIELD,
                    field_name="entity_id",
                )
            )

    def _validate_metric_values(
        self,
        source_record: OperationalSourceRecord,
        registry_entry: SourceRegistryEntry,
        issues: list[dict[str, Any]]
    ) -> None:
        for field_name in registry_entry.required_fields:
            if field_name not in source_record.metric_values:
                issues.append(
                    source_quality_issue(
                        SourceQualityDimension.COMPLETENESS,
                        SourceQualityStatus.MISSING_REQUIRED_FIELD,
                        field_name=field_name,
                    )
                )
                continue

            if source_record.metric_values[field_name] is None:
                issues.append(
                    source_quality_issue(
                        SourceQualityDimension.COMPLETENESS,
                        SourceQualityStatus.MISSING_REQUIRED_FIELD,
                        field_name=field_name,
                    )
                )

        numeric_fields = set(registry_entry.numeric_fields)
        numeric_fields.update(
            field_name
            for field_name in source_record.metric_values
            if _looks_numeric_field(field_name)
        )

        for field_name in numeric_fields:
            if field_name not in source_record.metric_values:
                continue

            value = source_record.metric_values[field_name]

            if value is None:
                continue

            numeric_value = _to_float(value)

            if numeric_value is None:
                issues.append(
                    source_quality_issue(
                        SourceQualityDimension.VALIDITY,
                        SourceQualityStatus.INVALID_METRIC_VALUE,
                        field_name=field_name,
                        message="Metric value must be numeric.",
                    )
                )
                continue

            if _looks_count_field(field_name) and numeric_value < 0:
                issues.append(
                    source_quality_issue(
                        SourceQualityDimension.VALIDITY,
                        SourceQualityStatus.INVALID_METRIC_VALUE,
                        field_name=field_name,
                        message="Count values cannot be negative.",
                    )
                )

            if (
                _looks_rate_or_percentage_field(field_name)
                and not 0 <= numeric_value <= 100
            ):
                issues.append(
                    source_quality_issue(
                        SourceQualityDimension.VALIDITY,
                        SourceQualityStatus.INVALID_METRIC_VALUE,
                        field_name=field_name,
                        message="Rate or percentage values must be between 0 and 100.",
                    )
                )

    def _validate_duplicate_source(
        self,
        context: TenantContext,
        source_record: OperationalSourceRecord,
        issues: list[dict[str, Any]]
    ) -> None:
        if self.source_repository is None:
            return

        duplicate = self.source_repository.find_duplicate(
            context,
            source_record
        )

        if duplicate is not None:
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.UNIQUENESS,
                    SourceQualityStatus.DUPLICATE_SOURCE,
                    message="Matching source already exists.",
                )
            )

    def _validate_freshness(
        self,
        source_record: OperationalSourceRecord,
        registry_entry: SourceRegistryEntry,
        issues: list[dict[str, Any]]
    ) -> None:
        if (
            registry_entry.freshness_threshold_hours is None
            or source_record.period_end is None
        ):
            return

        period_end = _as_utc(source_record.period_end)
        age_hours = (utc_now() - period_end).total_seconds() / 3600

        if age_hours > registry_entry.freshness_threshold_hours:
            issues.append(
                source_quality_issue(
                    SourceQualityDimension.TIMELINESS,
                    SourceQualityStatus.STALE_SOURCE,
                    field_name="period_end",
                    message="Source is older than freshness threshold.",
                )
            )

    def _validation_status(
        self,
        issues: list[dict[str, Any]]
    ) -> SourceValidationStatus:
        if not issues:
            return SourceValidationStatus.VALID

        if all(issue.get("code") == SourceQualityStatus.STALE_SOURCE.value for issue in issues):
            return SourceValidationStatus.WARNING

        return SourceValidationStatus.INVALID

    def _data_quality_status(
        self,
        issues: list[dict[str, Any]]
    ) -> SourceQualityStatus:
        if not issues:
            return SourceQualityStatus.VALID

        for issue in issues:
            if issue.get("code") != SourceQualityStatus.STALE_SOURCE.value:
                return SourceQualityStatus.from_value(issue.get("code", "valid"))

        return SourceQualityStatus.STALE_SOURCE

    def _result(
        self,
        context: TenantContext,
        source_record: OperationalSourceRecord,
        validation_status: SourceValidationStatus,
        data_quality_status: SourceQualityStatus,
        quality_issues: list[dict[str, Any]]
    ) -> SourceValidationResult:
        return SourceValidationResult(
            tenant_id=context.tenant_id,
            source_record_id=source_record.source_record_id,
            source_type=source_record.source_type,
            validation_status=validation_status,
            data_quality_status=data_quality_status,
            quality_issues=quality_issues,
            message=(
                "Source validation passed."
                if validation_status == SourceValidationStatus.VALID
                else "Source validation produced quality issues."
            ),
            metadata={
                "source_reference": source_record.source_reference,
                "issue_count": len(quality_issues),
            },
        )

    def _persist_validation_result(
        self,
        context: TenantContext,
        result: SourceValidationResult
    ) -> None:
        if self.validation_repository is None:
            return

        self.validation_repository.append(
            context,
            result
        )

    def _audit_result(
        self,
        context: TenantContext,
        action: str,
        source_record: OperationalSourceRecord,
        result: SourceValidationResult
    ) -> None:
        self._audit(
            context,
            action=action,
            source_record=source_record,
            status=result.validation_status.value,
            reason=result.data_quality_status.value,
            metadata={
                "data_quality_status": result.data_quality_status.value,
                "issue_count": len(result.quality_issues),
            },
        )

    def _audit(
        self,
        context: TenantContext,
        action: str,
        source_record: OperationalSourceRecord,
        status: str,
        reason: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        if self.audit_service is None:
            return

        self.audit_service.record(
            context,
            action=action,
            entity_type="operational_source",
            entity_id=source_record.source_record_id,
            metadata={
                "source_type": source_record.source_type.value,
                "source_reference": source_record.source_reference,
                "validation_status": status,
                "reason": reason,
                **(metadata or {}),
            },
        )


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_numeric_field(field_name: str) -> bool:
    normalized = field_name.lower()

    return any(
        token in normalized
        for token in [
            "score",
            "count",
            "rate",
            "percent",
            "percentage",
            "aht",
            "csat",
            "osat",
            "qa",
            "adherence",
            "attendance",
            "aux",
            "productivity",
            "conversion",
            "upt",
            "total",
        ]
    )


def _looks_count_field(field_name: str) -> bool:
    normalized = field_name.lower()

    return "count" in normalized or normalized.startswith("total_")


def _looks_rate_or_percentage_field(field_name: str) -> bool:
    normalized = field_name.lower()

    return any(
        token in normalized
        for token in [
            "rate",
            "percent",
            "percentage",
            "csat",
            "osat",
            "qa",
            "adherence",
            "attendance",
            "conversion",
        ]
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)
