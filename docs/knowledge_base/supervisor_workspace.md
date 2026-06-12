# Supervisor Workspace

## Purpose

Sprint 7 adds a backend-only Supervisor Workspace consumption layer. It turns
governed outputs from Sprints 1 through 6 into decision-ready, non-authoritative
read models that answer:

1. Who needs attention?
2. Why?
3. What should the supervisor do next?

The priority queue is the primary workspace artifact. The workspace preserves
the approved user-experience structure without implementing production UI:

- Supervisor Command Center
- Team Performance View
- Agent Performance Profile
- Employee Performance Timeline
- Coaching Workspace

## Backend Read Models First

Sprint 7 uses application-layer services and frozen read models. It does not
add React, HTML, FastAPI endpoints, dashboards, APIs, or another presentation
framework. A later presentation layer can consume these views without moving
business logic into the UI.

Workspace read models are:

- Derived from governed outputs.
- Dynamically generated for each authorized request.
- Non-authoritative and disposable.
- Frozen after construction.
- Traceable to upstream records and versions.
- Never persisted.

## Read Models

`SupervisorCommandCenterView` summarizes the current priority queue, priority
counts, leading impact drivers, open commitments, and overdue follow-ups.

`SupervisorPriorityQueueItem` copies the stored Risk Priority score and level,
the immutable risk and impact snapshots, governed driver references, coaching
metadata, and complete lineage. `recommended_action_type` mirrors the governed
priority level; it is not an automated recommendation.

`TeamPerformanceView` aggregates current employees and authoritative Risk,
Impact, Priority, KPI, and coaching metadata. Risk distributions use the
stored `RiskAssessmentResult.risk_level`; the workspace does not classify a
numeric risk score.

`AgentPerformanceProfileView` combines governed KPI, Risk, Impact, Priority,
Evidence, and coaching metadata for one employee.

`EmployeePerformanceTimelineView` merges governed performance, Risk,
Operational Impact, and Risk Priority event metadata in chronological order.
It creates no domain event.

`CoachingWorkspaceView` exposes linked Priority and Impact records, accepted
evidence references, opportunities, commitments, follow-ups, and permitted
note metadata. It never exposes note content or creates a coaching
recommendation.

## Service Responsibilities

- `SupervisorPriorityQueueService`: selects the latest supplied priority per
  employee, copies immutable snapshots, sorts by stored priority score, groups
  by stored priority level, and attaches lineage.
- `SupervisorProfileService`: assembles the employee profile from governed
  outputs without calculating KPI, Risk, Impact, Priority, or coaching results.
- `SupervisorTimelineService`: merges and sorts supplied governed event
  streams.
- `SupervisorCoachingWorkspaceService`: assembles coaching context and applies
  separate manager-only and leadership-only note permissions.
- `SupervisorWorkspaceService`: orchestrates the Command Center and Team
  Performance views and delegates employee-specific views.

The services receive governed records from callers. Sprint 7 adds no workspace
repository, migration, table, or persistence adapter.

## Permission Model

Workspace permissions extend the existing `RBACService`:

- `VIEW_SUPERVISOR_WORKSPACE`
- `VIEW_SUPERVISOR_PRIORITY_QUEUE`
- `VIEW_TEAM_PERFORMANCE_WORKSPACE`
- `VIEW_AGENT_PERFORMANCE_PROFILE`
- `VIEW_EMPLOYEE_TIMELINE`
- `VIEW_COACHING_WORKSPACE`
- `VIEW_PRIVATE_COACHING_NOTES`
- `VIEW_LEADERSHIP_NOTES`

Every request validates the existing `TenantContext`, requester identity, and
tenant ID. Access is denied by default. Standard workspace access does not
grant either sensitive-note permission.

Performance managers receive the standard workspace permissions and
manager-only note access. Leadership receives the standard permissions plus
manager-only and leadership-only note access. Governance administrators retain
all permissions. Existing non-workspace roles are not implicitly granted
workspace access.

## Restricted Data Suppression

Suppression occurs before read-model construction. The workspace removes:

- Customer comments and identifiers.
- Call transcripts and recordings.
- Raw source payloads.
- Private, manager-only, and leadership-only note content.
- Content references.
- PAN and CVV.

Only controlled identifiers, classifications, scores, version references,
lineage references, and permitted coaching metadata are returned. Evidence
references with restricted source markers are dropped. The existing PCI
redaction service masks valid PAN and labeled CVV values in remaining strings.

Notes expose only note ID, visibility classification, and lineage when the
requester has the required permission. `content_reference` is never copied to
a workspace view.

## Lineage Preservation

Workspace lineage preserves:

```text
KPI Result
    |
Risk Result and definition/rule versions
    |
Operational Impact Assessment, definition, factor, and threshold versions
    |
Risk Priority Assessment
    |
Workspace View
```

Evidence pack and artifact references, coaching lineage, commitment lineage,
follow-up lineage, and visible-note lineage are attached where available.
Views with authoritative records reject missing lineage. Valid empty
Command Center and Timeline responses are explicitly marked
`workspace_status:incomplete` rather than inventing upstream lineage.

## Audit Events

- `SUPERVISOR_WORKSPACE_VIEWED`
- `SUPERVISOR_PRIORITY_QUEUE_VIEWED`
- `TEAM_PERFORMANCE_VIEWED`
- `AGENT_PROFILE_VIEWED`
- `EMPLOYEE_TIMELINE_VIEWED`
- `COACHING_WORKSPACE_VIEWED`
- `SUPERVISOR_WORKSPACE_ACCESS_DENIED`
- `RESTRICTED_WORKSPACE_DATA_SUPPRESSED`
- `PRIVATE_NOTE_ACCESS_DENIED`
- `LEADERSHIP_NOTE_ACCESS_DENIED`
- `CROSS_TENANT_WORKSPACE_ACCESS_DENIED`

The existing KPI audit service and append-only SQLite audit table are reused.
Metadata contains identifiers, permission references, lineage references, and
suppression reason codes only. It never contains raw payloads, comments,
transcript or recording content, note content, PAN, CVV, or customer data.

## No-Persistence Rule

There are no workspace tables, repositories, migrations, or database writes
for read models. Only existing audit events are persisted. Integration tests
inspect SQLite schema after generating every view and reject any table whose
name contains `workspace`.

## Out Of Scope

- Production UI, React, static HTML, dashboards, and decorative charts.
- FastAPI endpoints or other new APIs.
- KPI, Risk, Impact, Priority, Evidence, or coaching calculation.
- Automated recommendations or coaching intelligence.
- AI, prediction, automation, workflow engines, queues, or schedulers.
- Microservices, event sourcing, streaming, or new frameworks.
- PeopleForce or other external integrations.
- Docker, Linux deployment, hosting, or production infrastructure.
