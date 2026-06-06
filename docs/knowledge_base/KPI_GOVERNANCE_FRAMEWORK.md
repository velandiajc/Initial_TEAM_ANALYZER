# KPI Governance Framework

## Purpose

Sprint 1 establishes KPI governance controls for TEAM_ANALYZER. It defines how KPI metadata is registered, owned, stewarded, lifecycle-managed, formula-versioned, approved, audited, and tenant-scoped.

Sprint 2 extends that foundation into a safe, controlled KPI calculation base:

Governed KPI Definition -> Approved Formula Version -> Safe Calculation Service -> Traceable KPI Result

This framework still does not provide dashboards, analytics, risk scoring, coaching engines, AI features, expression parsing, dynamic formula execution, or a generic formula DSL.

## Governance Models

| Model | Purpose |
|---|---|
| `TenantContext` | Required context for tenant-scoped governance access and user attribution. |
| `KPIDefinition` | Canonical KPI metadata including domain, lifecycle, owner, steward, creator, and timestamps. |
| `KPIDomain` | KPI domain classification such as customer experience, quality, workforce, productivity, sales, coaching, and operations. |
| `KPILifecycle` | Governed KPI lifecycle states: draft, pending approval, approved, active, retired, and archived. |
| `KPIThreshold` | Governed threshold metadata tied to a KPI and tenant. |
| `FormulaVersion` | Formula metadata, effective dating, lineage, approval status, and immutable approved formula content. |
| `KPICalculationRequest` | Tenant-scoped calculation request with KPI ID, period, scope, source data, and run ID. |
| `KPICalculationResult` | Traceable KPI result with formula lineage, period, scope, value, status, data quality, source reference, and run ID. |
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
- Only approved formulas may execute.
- Approved formula content is immutable.
- Effective formula overlap blocks approved formula resolution.
- Missing approved formulas block calculation.
- KPI calculation requires the explicit `calculate_kpi` permission.
- KPI result reads require the explicit `view_kpi_results` permission.
- All SQLite repository reads and writes are tenant-scoped.
- Calculation validates tenant boundaries across context, KPI, formula, source data, result, and audit events.
- Governance actions are recorded as audit events.
- Calculation actions are recorded as audit events.
- User attribution is captured through `TenantContext.user_id`.

## SQLite Persistence

`DatabaseService.initialize()` provisions:

- `kpi_definitions`
- `kpi_thresholds`
- `formula_versions`
- `kpi_audit_events`
- `kpi_calculation_results`

These tables are scoped by `tenant_id` and are separate from survey, agent, CSAT, and VOC data.

## Service Contracts

| Service | Responsibility |
|---|---|
| `KPIRegistryService` | Registers KPIs, updates ownership, adds thresholds, submits formula versions, approves formulas, changes lifecycle, and reads definitions. |
| `FormulaGovernanceService` | Explicit formula governance contract for formula submission and approval workflows. |
| `OwnershipService` | Explicit ownership contract for owner and steward changes. |
| `LifecycleService` | Explicit lifecycle contract for governed KPI lifecycle transitions. |
| `FormulaVersionService` | Resolves approved formulas for calculation periods, returns formula lineage, and detects effective-period conflicts. |
| `FormulaHandlerRegistry` | Maps approved formula handler keys to controlled calculation handlers without executing raw formula text. |
| `KPICalculationService` | Orchestrates permission checks, active KPI validation, formula resolution, handler execution, result persistence, and calculation audit events. |
| `KPIAuditService` | Records and reads audit events. |
| `RBACService` | Enforces governance roles and permissions. |
| `SQLiteKPIDefinitionRepository` | Persists KPI definitions, thresholds, and formula versions. |
| `SQLiteKPIAuditRepository` | Persists audit events. |
| `SQLiteKPICalculationResultRepository` | Persists traceable KPI calculation results and enforces result-view permissions. |

## Out Of Scope

Sprint 2 does not include dashboards, reporting, analytics, risk engines, coaching engines, AI features, predictive models, workspaces, microservices, event sourcing, message queues, schedulers, background jobs, API expansion, PostgreSQL, new frameworks, a generic formula DSL, expression parsing, runtime code generation, or dynamic formula execution.
