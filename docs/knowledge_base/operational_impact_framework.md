# Operational Impact Framework

## Purpose

Sprint 6 adds Operational Impact as a standalone governed bounded context.
It distinguishes business consequence from the severity already owned by the
Risk domain.

```text
Governed KPI Result
        |
        v
Governed Risk Result = severity
        |
        v
Operational Impact Assessment = business consequence
        |
        v
Risk Priority Assessment = combined action priority
```

Operational Impact does not replace Risk, calculate KPI values, or choose a
coaching action. It produces reproducible impact and priority records for later
human review.

## MVP Factors

The implementation supports the approved eight-factor vocabulary and activates
five factors in the reference workflow:

- Survey Volume
- Handled Contacts
- QA Critical Errors
- Attendance Instability
- Adherence Deviation
- Escalation Frequency
- Unresolved Coaching Commitments
- Repeated KPI Failure

Each active definition must have 5 to 8 active factors. Active factor weights
must total `1.0`. A factor source must be a governed `kpi:<id>` or `risk:<id>`
reference. Raw values and raw source payloads are not accepted.

## Scoring

Each factor normalizes its governed source value to a 0 to 100 score using its
versioned minimum, maximum, and direction. The assessment then calculates:

```text
Operational Impact Score =
sum(Normalized Factor Score * Factor Weight)
```

Impact classification:

- `LOW`: 0 through 24.99
- `MODERATE`: 25 through 49.99
- `HIGH`: 50 through 74.99
- `CRITICAL`: 75 through 100

Priority calculation:

```text
Risk Priority Score =
Risk Score * Operational Impact Score / 100
```

Priority classification:

- `MONITOR`: 0 through 24.99
- `COACH`: 25 through 49.99
- `ESCALATE`: 50 through 74.99
- `IMMEDIATE_INTERVENTION`: 75 through 100

## Governance Lifecycle

Definitions and factors use:

- `DRAFT`
- `APPROVED`
- `ACTIVE`
- `DEPRECATED`
- `RETIRED`

Only approved records can become active. The creator cannot approve their own
definition or factor. Weight and threshold changes require a new factor
version, which applies the same creator/approver separation.

Definition, factor, threshold, and weight versions are preserved in every
assessment snapshot. SQLite guards reject direct mutation of governed version
content while allowing lifecycle and approval fields to change.

## Lineage

An Operational Impact Assessment persists only when it contains:

- Definition ID and version.
- Factor IDs and versions.
- Threshold versions.
- Weight snapshots.
- Governed KPI and Risk Result IDs used by the active factors.
- A deterministic lineage ID derived from upstream lineage and versions.

A Risk Priority Assessment persists only when it contains:

- Risk Result ID.
- Risk definition and rule versions.
- Operational Impact Assessment ID and definition version.
- Immutable risk and impact score snapshots.
- A deterministic combined lineage ID.

Missing or inaccessible inputs are rejected. Rejections and access denials are
audited with sanitized metadata.

## Timeline

Operational Impact timeline events are append-only and material-change-only.
The first assessment establishes a baseline and does not create an event.
Low-to-moderate and monitor-to-coach movement is treated as noise. Changes
involving high/critical impact or escalate/immediate priority create one
immutable event.

## Permissions

- `create_operational_impact_definition`
- `approve_operational_impact_definition`
- `view_operational_impact`
- `calculate_operational_impact`
- `view_risk_priority`
- `calculate_risk_priority`

The existing `TenantContext` and `RBACService` enforce permissions. All
repositories require tenant context, reject cross-tenant writes, and filter
reads by tenant. Service read paths reject and audit inaccessible records.

## Audit Events

- `OPERATIONAL_IMPACT_DEFINITION_CREATED`
- `OPERATIONAL_IMPACT_DEFINITION_APPROVED`
- `OPERATIONAL_IMPACT_FACTOR_CREATED`
- `OPERATIONAL_IMPACT_FACTOR_APPROVED`
- `OPERATIONAL_IMPACT_CALCULATED`
- `OPERATIONAL_IMPACT_VIEWED`
- `OPERATIONAL_IMPACT_REJECTED`
- `OPERATIONAL_IMPACT_CALCULATION_FAILED`
- `OPERATIONAL_IMPACT_ACCESS_DENIED`
- `RISK_PRIORITY_CALCULATED`
- `RISK_PRIORITY_VIEWED`
- `RISK_PRIORITY_REJECTED`
- `RISK_PRIORITY_CALCULATION_FAILED`
- `RISK_PRIORITY_ACCESS_DENIED`
- `OPERATIONAL_IMPACT_TIMELINE_EVENT_CREATED`

Audit metadata contains identifiers, versions, classifications, snapshots, and
lineage only. The shared sanitizer removes raw payload, customer comment,
transcript, recording, coaching-note, private-note, PAN, CVV, and cardholder
fields. PCI redaction remains active for string values.

## Persistence

SQLite tables:

- `operational_impact_definitions`
- `operational_impact_factors`
- `operational_impact_assessments`
- `risk_priority_assessments`
- `operational_impact_timeline_events`

Assessments, priorities, and timeline events are insert-only. SQLite rejects
UPDATE and DELETE. Definition and factor rows cannot be deleted, and their
versioned business content cannot be changed in place.

## Architecture Alignment

- Preserves the modular monolith.
- Uses the established domain, application service, repository contract, and
  SQLite adapter pattern.
- Keeps Risk authoritative for severity and Operational Impact authoritative
  for consequence.
- Adds no API, UI, microservice, queue, scheduler, workflow engine, or runtime
  dependency.

## Security Restrictions

Operational Impact never consumes or persists:

- Raw CSV or Excel values.
- Raw operational payloads.
- Customer comments.
- Call transcripts or recordings.
- Shared, manager-only, leadership-only, or private coaching-note content.
- PAN, CVV, or cardholder data.

Only governed result identifiers and sanitized governance metadata cross the
application boundary.

## Out Of Scope

- Supervisor and leadership workspaces.
- Dashboard or frontend work.
- External APIs and integrations.
- AI, LLM, machine-learning, predictive, or recommendation behavior.
- Automated actions, workflows, queues, schedulers, or streaming.
- Deployment, hosting, Docker, and Linux production enablement.
