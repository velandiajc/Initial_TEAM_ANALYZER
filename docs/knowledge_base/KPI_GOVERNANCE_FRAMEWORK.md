# KPI Governance Framework

## Purpose

Sprint 1 establishes KPI governance controls for TEAM_ANALYZER. It defines how KPI metadata is registered, owned, stewarded, lifecycle-managed, formula-versioned, approved, audited, and tenant-scoped.

This framework is governance-only. It does not calculate KPI results, execute formulas, produce dashboards, or create risk/coaching engines.

## Governance Models

| Model | Purpose |
|---|---|
| `TenantContext` | Required context for tenant-scoped governance access and user attribution. |
| `KPIDefinition` | Canonical KPI metadata including domain, lifecycle, owner, steward, creator, and timestamps. |
| `KPIDomain` | KPI domain classification such as customer experience, quality, workforce, productivity, sales, coaching, and operations. |
| `KPILifecycle` | Governed KPI lifecycle states: draft, pending approval, approved, active, retired, and archived. |
| `KPIThreshold` | Governed threshold metadata tied to a KPI and tenant. |
| `FormulaVersion` | Formula metadata and approval status. Formulas are versioned but not executed. |
| `AuditEvent` | Immutable governance action record with tenant, actor, entity, action, timestamp, and metadata. |

## Governance Roles

| Role | Responsibility |
|---|---|
| KPI Owner | Accountable for KPI definition, ownership, thresholds, formula submission, and lifecycle readiness. |
| KPI Steward | Maintains governed KPI metadata, thresholds, and formula submissions. |
| KPI Approver | Reviews and approves formula versions and lifecycle movement. |
| Governance Admin | Full governance administration across KPI metadata actions within a tenant. |

## Required Controls

- `TenantContext` is required for all governance service and repository access.
- KPI owner and KPI steward are required on every KPI definition.
- Formula versions are submitted in `pending_approval` status.
- Formula creators cannot approve their own formula version.
- All SQLite repository reads and writes are tenant-scoped.
- Governance actions are recorded as audit events.
- User attribution is captured through `TenantContext.user_id`.

## SQLite Persistence

`DatabaseService.initialize()` provisions:

- `kpi_definitions`
- `kpi_thresholds`
- `formula_versions`
- `kpi_audit_events`

These tables are scoped by `tenant_id` and are separate from survey, agent, CSAT, and VOC data.

## Service Contracts

| Service | Responsibility |
|---|---|
| `KPIRegistryService` | Registers KPIs, updates ownership, adds thresholds, submits formula versions, approves formulas, changes lifecycle, and reads definitions. |
| `FormulaGovernanceService` | Explicit formula governance contract for formula submission and approval workflows. |
| `OwnershipService` | Explicit ownership contract for owner and steward changes. |
| `LifecycleService` | Explicit lifecycle contract for governed KPI lifecycle transitions. |
| `KPIAuditService` | Records and reads audit events. |
| `RBACService` | Enforces governance roles and permissions. |
| `SQLiteKPIDefinitionRepository` | Persists KPI definitions, thresholds, and formula versions. |
| `SQLiteKPIAuditRepository` | Persists audit events. |

## Out Of Scope

Sprint 1 does not include KPI calculations, formula execution, KPI results, analytics, dashboards, risk scoring, coaching engines, FastAPI routes, scheduled workers, PostgreSQL, lineage, snapshots, or AI features.
