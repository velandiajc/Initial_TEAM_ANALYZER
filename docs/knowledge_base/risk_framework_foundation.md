# Risk Framework Foundation

## Purpose

Sprint 4 adds a governed risk framework foundation for TEAM_ANALYZER. It creates tenant-scoped risk definitions, rule versions, deterministic rule execution, traceable risk assessment results, RBAC enforcement, and audit events.

This foundation is intentionally limited to rule governance and assessment infrastructure. It does not add dashboards, coaching, recommendations, AI, predictive scoring, schedulers, queues, microservices, dynamic execution, expression parsing, or DSLs.

## Runtime Boundaries

- Risk logic remains inside the existing modular monolith.
- Risk definitions are tenant-scoped business objects.
- Risk rules are versioned and require approval by someone other than the creator.
- Rule execution is allowed only when the risk definition is active and exactly one approved active rule covers the assessment period.
- Rule behavior is selected through a registered Python handler key.
- The framework does not use `eval()`, `exec()`, `compile()`, expression parsing, runtime code generation, or arbitrary DSL execution.

## Governance Objects

Risk definitions capture:

- Tenant
- Risk definition ID
- Name and category
- Owner and steward
- Lifecycle
- Metadata

Risk rule versions capture:

- Tenant
- Risk definition ID
- Version number
- Registered handler key
- Structured parameters
- Approval status
- Approval metadata
- Active flag
- Effective period
- Superseded rule lineage

Approved risk rules are immutable for core execution fields. New logic must be submitted as a new rule version.

## Execution Traceability

Risk assessment results persist:

- Tenant
- Risk definition ID
- Rule version ID and version number
- Entity type and entity ID
- Assessment period
- Risk level
- Reason
- Evidence
- Source reference
- Assessment run ID

Audit events are emitted for risk definition registration, rule submission, rule approval, rule activation, lifecycle changes, assessment request/start/rule selection/completion/rejection/failure, and result views.

## Current Handler Capability

The first approved handler is `threshold`. It compares one governed metric value using one supported operator:

- `lt`
- `lte`
- `gt`
- `gte`
- `eq`
- `neq`
- `between`

Example rule parameters:

```json
{
  "metric_name": "avg_csat",
  "operator": "lt",
  "threshold": 80,
  "risk_level": "critical",
  "default_risk_level": "low",
  "reason": "Average CSAT below governed threshold."
}
```

## Explicitly Out Of Scope

- Dashboards
- Coaching sessions
- SMART commitments
- Supervisor recommendations
- AI or LLM interpretation
- Predictive models
- Dynamic rule execution
- `eval()`, `exec()`, `compile()`
- DSLs or expression parsers
- Microservices
- Queues
- Schedulers
