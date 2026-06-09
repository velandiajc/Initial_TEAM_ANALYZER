# Risk Framework Foundation

## Purpose

Sprint 4 adds a governed risk framework foundation for TEAM_ANALYZER. It creates tenant-scoped risk definitions, versioned risk rules, deterministic risk evaluation, numeric risk scoring, risk classification, traceable risk results, RBAC enforcement, and audit events.

This foundation remains inside the existing modular monolith. It does not add dashboards, UI, CLI commands, coaching workflows, recommendations, AI, predictive models, schedulers, queues, background jobs, microservices, dynamic rule execution, expression parsers, or DSLs.

## Approved Risk Chain

Risk evaluation follows the approved chain:

1. Trusted KPI Results
2. Risk Evaluation
3. Risk Classification
4. Risk Scoring
5. Risk Traceability

Risk evaluation consumes governed KPI Results. Raw caller-supplied `metric_values` are not accepted as trusted risk input. Metric values may exist inside the service only after they have been resolved from tenant-scoped KPI calculation results.

## KPI Result Boundary

Risk evaluation requests must reference governed KPI Result IDs or pass governed KPI Result objects for validation. The assessment service validates:

- KPI Result tenant matches the `TenantContext`.
- KPI Result exists when referenced by ID.
- KPI Result status is `success`.
- KPI Result data quality is trusted.
- KPI Result contains a numeric value.
- KPI Result period is inside the risk evaluation period.

Handlers receive only service-resolved metric values keyed by KPI ID.

## Governance Lifecycle

Risk definition and rule governance uses these approved lifecycle values:

- `draft`
- `review`
- `approved`
- `active`
- `deprecated`
- `retired`

Legacy stored values are normalized safely:

- `pending_approval` reads as `review`.
- `archived` reads as `deprecated`.
- legacy `moderate` risk level reads as `medium`.

## Risk Result Lineage

Every persisted risk result includes:

- Tenant ID
- Risk definition ID and risk definition version
- Risk rule version ID and rule version number
- KPI result IDs used for evaluation
- KPI formula versions associated with those KPI Results
- Source record IDs when available
- Source references and validation/data quality lineage when available
- Lineage ID
- Numeric `risk_score`
- Classified `risk_level`
- Evidence references and reason text

Only lineage references and metadata are stored. Raw source payloads, raw metric payloads, customer PII, secrets, and credentials must not be persisted in risk results or audit metadata.

## Risk Score And Level

`risk_score` is a deterministic numeric score. `risk_level` is the public classification:

- `low`
- `medium`
- `high`
- `critical`

The foundation threshold handler uses simple deterministic defaults unless a governed rule supplies explicit scores:

- Low: `25.0`
- Medium: `50.0`
- High: `75.0`
- Critical: `100.0`

This is not predictive scoring.

## Audit Events

Approved risk audit event names are:

- `RISK_EVALUATION_REQUESTED`
- `RISK_EVALUATION_STARTED`
- `RISK_RULE_SELECTED`
- `RISK_EVALUATION_COMPLETED`
- `RISK_EVALUATION_FAILED`
- `RISK_EVALUATION_REJECTED`
- `RISK_RESULT_VIEWED`
- `RISK_ACCESS_DENIED`

Audit metadata must stay tenant-scoped and must not include raw metric payloads, raw source data, secrets, or sensitive values.

## RBAC Permissions

Risk access is controlled by explicit risk permissions:

- `evaluate_risk`
- `view_risk_results`
- `manage_risk_definitions`
- `manage_risk_rules`

Risk evaluation requires `evaluate_risk`. Risk result retrieval requires `view_risk_results`. Risk definition creation and lifecycle changes require `manage_risk_definitions`. Risk rule submission, approval, activation, and versioning require `manage_risk_rules`.

## Future Work

Operational Impact / Operational Weight is deferred.

Risk Priority Score = Risk Score × Operational Impact Score

Do not implement Operational Impact Score in this patch.

## Explicitly Out Of Scope

- Dashboards
- UI
- CLI
- Coaching workflows
- Recommendations
- AI
- Predictive models
- Operational Impact scoring implementation
- Dynamic rule execution
- `eval()`
- `exec()`
- `compile()`
- DSLs
- Expression parsers
- Microservices
- Queues
- Schedulers
- Background jobs
- PostgreSQL migration
- New frameworks
