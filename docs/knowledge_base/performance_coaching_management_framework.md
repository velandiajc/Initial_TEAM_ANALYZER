# Performance and Coaching Management Foundation

## Purpose

Sprint 5 adds the governed Performance Management bounded context to
TEAM_ANALYZER. It records human performance-management actions after governed
KPI, risk, and evidence results exist.

The authoritative chain is:

```text
Operational Source
-> KPI Result
-> Risk Result
-> Evidence Pack
-> Performance Opportunity
-> Coaching Session
-> Commitment
-> Follow-Up
-> Employee Performance Timeline
```

This foundation records what action occurred. It does not decide what coaching
should occur.

## Inputs

Performance opportunity and coaching session creation require:

- A `TenantContext`.
- An accepted `EvidencePack`.
- A governed `RiskAssessmentResult`.
- Matching tenant and employee references.
- Evidence pack references to the risk result and its KPI results.
- A non-empty upstream `lineage_id`.
- Human-provided opportunity, session owner, and coaching version values.

## Outputs

The bounded context persists:

- `PerformanceOpportunity`
- `CoachingSession`
- `CoachingCommitment`
- `CoachingFollowUp`
- `CoachingNote`
- `EmployeePerformanceTimelineEvent`

Timeline events store source identifiers and event classifications only. They
do not copy coaching notes, evidence content, free-form narratives, customer
PII, or employee PII.

## Dependencies

Sprint 5 extends existing project capabilities only:

- Python dataclasses and enums for domain records.
- Existing `TenantContext` and `RBACService`.
- Existing `KPIAuditService` and SQLite audit repository.
- Existing `RiskAssessmentResult`.
- Existing passive `EvidencePack`.
- Existing `DatabaseService` and SQLite.
- Pytest.

No framework or runtime dependency was added.

## Business Rules

### Lineage

Persistence rejects missing:

- `lineage_id`
- `evidence_pack_id`
- `risk_result_id`

Evidence must be human-reviewed with `ACCEPTED` status. The evidence pack must
reference the exact risk result and the KPI results used by that risk result.
Tenant and employee references must match.

### Immutable Session Snapshots

Session creation copies:

- Risk result ID.
- Risk score.
- Risk level.
- Risk definition classification.
- Risk definition version.
- Risk rule version.
- Evidence pack ID.
- Evidence pack creation timestamp as its version marker.
- Evidence artifact identifiers.
- Coaching version.
- Lineage ID.

Domain entities are frozen. Repository comparisons and SQLite triggers reject
changes to historical or snapshot fields.

### Lifecycle

Explicit transition maps govern:

- Performance opportunity status.
- Coaching session status.
- Commitment status.
- Follow-up status.

Status transitions return new domain values. The persisted current status may
change only through governed service methods. Each coaching, commitment, and
follow-up transition creates an append-only timeline event so historical state
changes remain reconstructable.

### Historical Integrity

Delete operations are absent from repository contracts. SQLite `BEFORE DELETE`
triggers reject direct deletion from all Sprint 5 tables.

Coaching notes and timeline events are append-only. SQLite triggers reject all
updates. Opportunity, session, commitment, and follow-up triggers allow only
governed mutable status or attribution fields and reject historical changes.

### Timeline Authority

`EmployeePerformanceTimelineEvent` is the authoritative chronological employee
performance history. Supported sources are:

- `KPI`
- `RISK`
- `EVIDENCE`
- `COACHING`
- `FOLLOWUP`
- `COMMITMENT`
- `MANUAL`

Duplicate source events are rejected by a tenant-scoped uniqueness constraint.

## Security Controls

### Tenant Isolation

Every Sprint 5 entity includes `tenant_id`. Repositories require
`TenantContext`, reject cross-tenant writes, and filter all reads by tenant.
Audit events use the same tenant context.

### RBAC

Implemented permissions:

- `view_coaching_session`
- `create_coaching_session`
- `edit_coaching_session`
- `create_commitment`
- `update_commitment`
- `create_followup`
- `view_performance_timeline`
- `view_private_coaching_note`

Performance coach, performance manager, leadership, and governance admin roles
receive least-privilege permission sets.

### Note Visibility

Visibility is immutable:

- `SHARED` requires session view permission.
- `MANAGER_ONLY` additionally requires private-note permission and a manager,
  leadership, or governance-admin role.
- `LEADERSHIP_ONLY` additionally requires private-note permission and a
  leadership or governance-admin role.

Session access alone never grants private-note access.

### Audit

Implemented events:

- `COACHING_SESSION_CREATED`
- `COACHING_SESSION_UPDATED`
- `COACHING_SESSION_CLOSED`
- `COACHING_OPPORTUNITY_CREATED`
- `COMMITMENT_CREATED`
- `COMMITMENT_COMPLETED`
- `COMMITMENT_MISSED`
- `FOLLOWUP_CREATED`
- `NOTE_CREATED`
- `PRIVATE_NOTE_VIEWED`
- `TIMELINE_EVENT_CREATED`
- `COACHING_ACCESS_DENIED`
- `COACHING_RECORD_MODIFICATION_REJECTED`

Audit metadata contains identifiers, status, versions, and lineage references.
It excludes note contents and narrative payloads through both service design
and the existing audit sanitizer.

## Database Changes

SQLite tables:

- `performance_opportunities`
- `coaching_sessions`
- `coaching_commitments`
- `coaching_followups`
- `coaching_notes`
- `performance_timeline_events`

All keys and relationships are tenant-scoped. Foreign keys link opportunities,
sessions, commitments, follow-ups, and notes. SQLite foreign-key enforcement is
enabled on every connection.

## Governance Alignment

### Architecture

- Remains a modular monolith.
- Uses domain, application, and persistence layers.
- Adds no API, UI, microservice, queue, scheduler, or event-sourcing layer.

### Security

- Applies least privilege, tenant isolation, visibility classification, audit
  trails, and defense in depth.
- Treats performance records as confidential workforce information.

### Data Governance

- Requires trusted references and complete lineage.
- Preserves historical reproducibility.
- Uses references rather than duplicating source or evidence content.

### Engineering

- Keeps business rules in domain and application services.
- Keeps SQL in repository adapters.
- Uses typed contracts and focused tests.

### DevOps

- Adds no dependency or hidden infrastructure.
- Keeps changes within the approved Sprint 5 directories.
- Supports unit, integration, security, and regression validation.

## Known Limitations

- Evidence persistence remains outside Sprint 5 because Sprint 4.1 provides
  passive domain models only. Services consume governed `EvidencePack` values
  at the application boundary.
- The evidence pack creation timestamp is the current immutable version marker
  because Sprint 4.1 does not yet define an evidence version field.
- This batch-oriented repository does not expose Sprint 5 through an API or UI.
- Employee hierarchy scope below tenant level is not yet modeled.

## Explicitly Out of Scope

- Coaching Intelligence.
- Recommendations or action-plan generation.
- AI or LLM features.
- Operational Impact scoring.
- Dashboards or workspaces.
- Notifications, messaging, email, or calendars.
- Workflow engines, automation, queues, or schedulers.
- Automatic opportunity, session, commitment, or follow-up creation.

## Future Improvements

Future approved sprints may add Operational Impact and Coaching Intelligence
after they can consume this governed history. Those capabilities must preserve
the immutable snapshots, tenant boundaries, audit controls, and timeline
authority established here.
