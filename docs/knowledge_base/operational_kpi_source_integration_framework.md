# Operational KPI Source Integration Framework

## Purpose

Sprint 3 adds an operational source governance foundation to TEAM_ANALYZER. It ensures KPI calculations can be tied to registered, validated, tenant-scoped operational data with source versioning, lineage, source ownership, stewardship, auditability, and explicit security controls.

The integration path is:

Operational Source Registry -> Validated Source Record -> KPI Source Eligibility -> KPI Calculation Result Metadata

## Sprint 3 Scope

Sprint 3 introduces:

- Operational source domain models.
- Source registry ownership and stewardship.
- Tenant-scoped SQLite source persistence.
- Source validation events.
- Source validation service rules.
- KPI source eligibility checks before formula execution.
- Source-aware KPI calculation metadata.
- RBAC permissions for source governance.
- Sanitized audit events for source registration, validation, usage, and denial.

## Operational Source Model

`OperationalSourceRecord` represents a governed operational data source instance used by KPI calculations. Each record includes:

- `tenant_id`
- `source_type`
- `source_reference`
- `source_version`
- `lineage_id`
- `period_start`
- `period_end`
- `entity_type`
- `entity_id` when the scope is not tenant-level
- `metric_values`
- `validation_status`
- `data_quality_status`

`source_version` and `lineage_id` are required so downstream KPI results can identify exactly which source generation and lineage produced a calculation.

## Source Registry

`SourceRegistryEntry` is the governance record for a source type. It defines:

- Source owner.
- Source steward.
- Allowed entity scopes.
- Required metric fields.
- Numeric metric fields.
- Optional freshness threshold.
- Active or inactive status.

Only one active source type can be registered per tenant and source type.

## Source Ownership And Stewardship

Every registered source type requires:

- `source_owner`: accountable for the source definition and business use.
- `source_steward`: responsible for source quality, field expectations, and operational readiness.

Missing owner or steward values are rejected at the model and service layer.

## Source Versioning

`source_version` identifies the version of the source extract, source contract, source schema, or upstream generation used by an operational record. KPI source eligibility blocks source-backed calculation when the version is missing.

## Source Lineage

`lineage_id` identifies the traceable path from upstream operational data to the validated source record. KPI result persistence blocks source-backed result metadata when lineage is missing.

## Validation Status Vs Data Quality Status

`validation_status` describes the validation outcome:

- `valid`
- `warning`
- `invalid`

`data_quality_status` describes the primary quality classification:

- `valid`
- `missing_required_field`
- `invalid_period`
- `tenant_mismatch`
- `unsupported_source_type`
- `duplicate_source`
- `stale_source`
- `invalid_entity_scope`
- `invalid_metric_value`
- `data_conflict`

These fields are separate so a source can have a validation outcome and a specific quality reason.

## Data Quality Dimensions

Every quality issue maps to one of six dimensions:

- `accuracy`
- `completeness`
- `consistency`
- `timeliness`
- `uniqueness`
- `validity`

This keeps source quality reporting aligned to governed quality categories instead of ad hoc error strings.

## Source Validation Rules

The source validation service enforces:

- `TenantContext` is required.
- Source tenant must match context tenant.
- Source type must exist in the registry.
- Source type must be active.
- `source_reference` is required.
- `source_version` is required.
- `lineage_id` is required.
- `period_start` is required.
- `period_end` is required.
- `period_start` must be before or equal to `period_end`.
- Entity scope must be allowed by the registry entry.
- `entity_id` is required unless `entity_type` is tenant.
- Registry required fields must exist in `metric_values`.
- Required metric values cannot be null.
- Numeric fields must be valid numbers.
- Count fields cannot be negative.
- Rate and percentage fields must be between 0 and 100 when identifiable.
- Stale sources are detected using `freshness_threshold_hours`.
- Duplicate sources are detected by tenant, source type, entity scope, entity ID, period, and source reference.

Valid and warning source records may be persisted. Invalid source records persist validation events but are not saved as eligible operational sources.

## KPI Source Eligibility Rules

KPI source eligibility runs before formula handler execution when a calculation request provides `source_records`, `source_record_ids`, or `source_references`.

Eligibility blocks calculation when:

- Source lineage is missing.
- Source version is missing.
- Source tenant does not match context tenant.
- Source validation failed.
- Source type is unsupported.
- Source type is inactive.
- Source is duplicate.
- Required source fields are missing.
- Source period is invalid.
- Source quality is stale or otherwise not valid.

Eligible source metadata is merged into KPI result metadata:

- `source_record_ids`
- `source_references`
- `source_types`
- `source_version`
- `lineage_id`
- `source_validation_status`
- `source_quality_summary`

## Security Controls

Sprint 3 source persistence and services enforce:

- Tenant context required for reads and writes.
- Cross-tenant writes rejected.
- Cross-tenant reads return `None` or empty results.
- Source validation rejects tenant mismatch.
- KPI source eligibility rejects tenant mismatch.
- KPI result persistence rejects source-backed results without lineage or version metadata.
- Unauthorized source registration is rejected.
- Unauthorized source validation is rejected.
- Unauthorized source view is rejected.
- Unauthorized or cross-tenant source usage writes `SOURCE_ACCESS_DENIED`.

## RBAC Permissions

Sprint 3 adds:

- `register_source_type`
- `validate_operational_source`
- `view_operational_source`

`governance_admin` can register, validate, and view operational sources. Existing KPI permissions such as `calculate_kpi` and `view_kpi_results` remain unchanged.

## Audit Events

Sprint 3 supports:

- `SOURCE_REGISTERED`
- `SOURCE_VALIDATED`
- `SOURCE_REJECTED`
- `SOURCE_VALIDATION_FAILED`
- `SOURCE_USED_FOR_CALCULATION`
- `SOURCE_ACCESS_DENIED`

Audit metadata is summary-only and avoids raw operational payloads.

## PII And Audit Restrictions

Audit metadata must not include:

- Raw customer comments.
- Customer PII.
- Employee PII.
- Full operational payloads.
- Authentication data.
- Secrets.

The audit service sanitizes sensitive metadata keys before events are persisted.

## Known Limitations

- Source type support is enum-based and intentionally limited to operational KPI source categories.
- Source freshness uses source period end timestamps and the registry threshold.
- Rate and percentage validation is based on identifiable field names.
- Duplicate detection is scoped to persisted source records.
- Source validation does not perform external source reconciliation.

## Future Work

Future sprints may add:

- Richer source lineage graphs.
- Source reconciliation reports.
- Source health dashboards.
- Field-level schema versioning.
- Source contract migration workflows.
- Operational analytics outputs based on validated sources.

## Explicit Out Of Scope

Sprint 3 does not add:

- Analytics dashboards.
- Risk Engine features.
- Coaching engines.
- AI interpretation.
- New APIs.
- Background jobs.
- External data connectors.
- Dynamic formula execution.
- Generic formula expression parsing.
