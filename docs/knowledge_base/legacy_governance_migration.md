# Legacy Governance Migration

## Scope

Sprint 5.1 places the legacy agent, survey, and survey-ingestion workflows
under the governance mechanisms already used by the Sprint 1 through Sprint 5
domains.

No parallel security model was introduced.

## Controls

Legacy services now require:

- a valid `TenantContext`;
- an existing `RBACService` permission;
- tenant-filtered reads and writes; and
- an existing `KPIAuditService` for success and access-denied events.

The added permissions are:

- `manage_agent_records`;
- `view_agent_records`;
- `ingest_surveys`; and
- `view_surveys`.

Governance administrators receive all permissions. KPI owners can manage and
view the legacy records. KPI stewards can ingest and view surveys and view
agents. KPI approvers have read-only legacy visibility.

## Database Migration

The `agents`, `agent_aliases`, and `surveys` tables now use tenant-aware
composite primary keys. Existing pre-tenant rows are migrated in place to the
configured `legacy_tenant_id`, which defaults to `legacy-local`.

The local pipeline obtains its tenant and user from:

- `TEAM_ANALYZER_TENANT_ID`; and
- `TEAM_ANALYZER_USER_ID`.

Defaults preserve the current local command-line workflow. Production
deployments must set explicit values through the approved secret and
configuration mechanism.

## Audit Events

The governed workflow records agent upserts and lookups, survey ingestion and
views, discovery completion, and denied access attempts. Audit metadata does
not contain raw survey comments or cardholder data.

## Compatibility

The migration stays inside the existing modular monolith, SQLite persistence,
tenant context, RBAC, and audit abstractions. It adds no API, framework,
service, queue, scheduler, or workflow engine.
