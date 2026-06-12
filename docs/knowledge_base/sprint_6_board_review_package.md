# Sprint 6 Board Review Package

## Executive Summary

Sprint 6 implements a governed Operational Impact bounded context without
changing the Risk, KPI, coaching, evidence, or legacy operational domains.
Risk remains authoritative for severity. Operational Impact records business
consequence. Risk Priority combines immutable risk and impact snapshots for
human action prioritization.

The implementation preserves the modular monolith and existing repository
structure. It adds no UI, API, framework, service boundary, queue, scheduler,
AI feature, deployment target, or runtime dependency.

## Branch

`feature/operational-impact-framework`

The branch is committed and pushed in pull request #24. It has not been
merged.

## Files Created

- `app/domain/operational_impact/__init__.py`
- `app/domain/operational_impact/entities.py`
- `app/domain/operational_impact/rules.py`
- `app/domain/operational_impact/value_objects.py`
- `app/application/operational_impact/__init__.py`
- `app/application/operational_impact/services/__init__.py`
- `app/application/operational_impact/services/_service.py`
- `app/application/operational_impact/services/assessment_service.py`
- `app/application/operational_impact/services/definition_service.py`
- `app/application/operational_impact/services/factor_service.py`
- `app/application/operational_impact/services/priority_service.py`
- `app/application/operational_impact/services/timeline_service.py`
- `app/infrastructure/persistence/operational_impact/__init__.py`
- `app/infrastructure/persistence/operational_impact/repositories.py`
- `tests/unit/operational_impact/__init__.py`
- `tests/unit/operational_impact/test_operational_impact_domain.py`
- `tests/integration/operational_impact/__init__.py`
- `tests/integration/operational_impact/support.py`
- `tests/integration/operational_impact/test_operational_impact_workflow.py`
- `tests/security/operational_impact/__init__.py`
- `tests/security/operational_impact/test_operational_impact_security.py`
- `docs/knowledge_base/operational_impact_framework.md`
- `docs/knowledge_base/sprint_6_board_review_package.md`

## Files Modified

- `app/core/permissions.py`
- `app/services/database_service.py`
- `app/services/kpi_audit_service.py`

## Domain Models Added

- `OperationalImpactDefinition`
- `OperationalImpactFactor`
- `OperationalImpactAssessmentRequest`
- `OperationalImpactAssessment`
- `RiskPriorityAssessment`
- `OperationalImpactTimelineEvent`
- Governance, direction, impact-level, priority-level, and audit-event enums

## Services Added

- `OperationalImpactDefinitionService`
- `OperationalImpactFactorService`
- `OperationalImpactAssessmentService`
- `RiskPriorityService`
- `OperationalImpactTimelineService`

## Repositories Added

Tenant-scoped protocols and SQLite adapters were added for:

- Operational Impact definitions
- Operational Impact factors
- Operational Impact assessments
- Risk priority assessments
- Operational Impact timeline events

## SQLite Changes

Tables added:

- `operational_impact_definitions`
- `operational_impact_factors`
- `operational_impact_assessments`
- `risk_priority_assessments`
- `operational_impact_timeline_events`

SQLite triggers prohibit deletion from all five tables. Assessment, priority,
and timeline rows prohibit all updates. Definition and factor version content,
including weights, thresholds, source references, and version identifiers,
cannot be changed in place.

## Permissions Added

- `CREATE_OPERATIONAL_IMPACT_DEFINITION`
- `APPROVE_OPERATIONAL_IMPACT_DEFINITION`
- `VIEW_OPERATIONAL_IMPACT`
- `CALCULATE_OPERATIONAL_IMPACT`
- `VIEW_RISK_PRIORITY`
- `CALCULATE_RISK_PRIORITY`

Permissions extend the existing governance roles and `RBACService`; no second
security model was introduced.

## Audit Events Added

- Definition and factor creation/approval
- Impact calculation, view, rejection, failure, and access denial
- Priority calculation, view, rejection, failure, and access denial
- Material Operational Impact timeline creation

## Security Controls Added

- Tenant-scoped reads and writes for all new repositories.
- Cross-tenant service reads reject and create access-denied audit events.
- Separate create, approve, calculate, and view permissions.
- Creator/approver separation for definitions and factors.
- Governed-result-only calculation inputs.
- Complete-lineage persistence gates.
- Immutable definition, factor, assessment, priority, and timeline history.
- Audit metadata denylisting for transcripts, recordings, cardholder fields,
  private/coaching notes, comments, and raw payloads.

## PCI/Data Protection Controls Preserved

- Existing PAN and CVV redaction remains active for audit string values.
- Existing SQLite PCI persistence triggers remain active.
- No transcript, recording, customer comment, note content, raw source value,
  PAN, CVV, or cardholder-data field was added to the new domain.
- Existing Sprint 5.1 PCI regression tests remain part of the full suite.

## Tests Added

Sprint 6 adds 40 focused tests covering:

- Required governance fields, weights, thresholds, and versions.
- Creator/approver separation.
- Score normalization and impact/priority classifications.
- Definition and factor lifecycle.
- KPI Result to Impact Assessment flow.
- Risk Result to Priority Assessment flow.
- Immutable snapshots and database history.
- Material-change timeline creation and noise suppression.
- RBAC denials, tenant isolation, and access-denied audits.
- Missing lineage/version persistence rejection.
- Audit metadata sanitization and forbidden input rejection.

## Validation Results

- Focused Sprint 6 suite: 40 passed.
- Full release-gate regression suite: 318 passed in 299.92 seconds.
- Existing Sprint 1-5.1 regression coverage: 278 passed within the full suite.
- Python compilation: passed.
- SQLite schema smoke test: passed.
- `git diff --check`: passed.
- Bandit 1.8.6 on Python 3.12: zero findings.
- `pip-audit -r Requirements.txt`: no known vulnerabilities.
- Gitleaks no-git scan of 229 repository-visible files: no leaks.

Architecture, security, data-governance, engineering, and DevOps alignment:

- Existing modular-monolith boundaries are preserved.
- Existing tenant, RBAC, audit, PCI, and dependency controls are reused.
- Only governed KPI and Risk Results are consumed.
- No raw-data persistence path or duplicate calculation model was introduced.
- CI configuration and dependency files require no Sprint 6 change.

## Risks

- Employee hierarchy authorization below the tenant boundary remains outside
  the current platform model.
- The five-factor reference configuration depends on governed KPI definitions
  being available and consistently scoped to the employee and period.
- Thresholds are normalized linearly; alternative approved normalization
  methods require new governed factor versions in a future sprint.
- Remote GitHub Actions results remain unavailable until a pull request runs.

## Open Items

- Engineering must review service boundaries and scoring rules.
- Security must review tenant-denial auditing and immutable SQLite triggers.
- QA must independently rerun the complete regression suite.
- DevOps must confirm the remote security workflow on the pull request.
- The Executive Board must approve before merge.

## Recommendation

Advance to Engineering, Security, QA, DevOps, and Executive Board review.

Do not merge until all remote checks and required departmental approvals pass.
