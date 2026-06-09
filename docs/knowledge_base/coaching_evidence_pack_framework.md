# Coaching Evidence Pack Framework

## Purpose

The Coaching Evidence Pack Framework defines a passive, governed structure for
organizing reviewed evidence references before future coaching work begins. It
supports evidence traceability, review lifecycle, and consistent presentation of
supporting references.

This is pre-Sprint 5 foundation work. It is not Coaching Intelligence and does
not create coaching decisions, recommendations, AI summaries, or automated
plans.

## Passive Evidence Organization

An evidence pack is a container. It groups:

- Reviewed evidence artifact identifiers.
- Supporting KPI result identifiers.
- Supporting Risk result identifiers.
- Optional governance notes.
- A root cause category label.

The pack does not interpret the evidence. It does not judge agent behavior,
calculate coaching outcomes, recommend commitments, or generate supervisor
strategy.

## Evidence Traceability

Each pack includes `tenant_id`, `evidence_pack_id`, evidence artifact
references, KPI references, Risk references, review status, sensitivity, and
root cause category. These fields make the pack traceable without copying raw
content into the pack.

Traceability expectations:

- Evidence artifact identifiers should point to governed metadata records.
- KPI references should point to governed KPI results.
- Risk references should point to governed Risk results.
- Human review status should be visible before any future coaching use.
- Raw evidence remains outside the pack.

## Evidence Presentation

The pack template is designed for consistent presentation of approved reference
sets. It can help a supervisor or reviewer see which artifacts, KPI results, and
Risk results are associated with a future coaching workflow.

Presentation does not mean content extraction. The pack must not include
transcript text, audio content, raw QA form content, customer statements, PII, or
raw evidence files.

## Human Review Requirement

`human_review_required` must always be `true`. Evidence packs are not approved
or accepted automatically. Future services must preserve the rule that human
review is required before evidence references support any coaching workflow.

## Approved Template Fields

The structure-only template contains:

- `evidence_pack_id`
- `tenant_id`
- `agent_id`
- `created_at`
- `review_status`
- `sensitivity`
- `human_review_required`
- `evidence_artifacts`
- `supporting_kpis`
- `supporting_risks`
- `root_cause_category`
- `notes`

The template contains no real data, customer data, transcript text, AI output,
recommendations, coaching scores, or generated plans.

## Root Cause Categories

Approved root cause categories:

- `SKILL`
- `KNOWLEDGE`
- `BEHAVIOR`
- `EXECUTION_DISCIPLINE`
- `ACCOUNTABILITY`
- `EXTERNAL_FACTOR`
- `UNKNOWN`

The category is a review label only. It does not make a coaching decision.

## Supporting KPI References

`supporting_kpis` stores identifiers for governed KPI results that may help
explain why an evidence pack exists. It does not copy KPI calculation details,
source data, or sensitive workbook content.

## Supporting Risk References

`supporting_risks` stores identifiers for governed Risk results that may provide
context. It does not alter risk scoring, create new risk results, or approve
evidence automatically.

## What The Pack Is Not

The coaching evidence pack is not:

- Coaching decisioning.
- Recommendations.
- AI.
- Transcript storage.
- Raw evidence storage.
- Audio or video storage.
- A generated coaching plan.
- A coaching score.
- A background processing job.
- A scheduler or queue.

## Future Sprint 5 Readiness

This framework prepares Sprint 5 by defining reviewed evidence references and
pack structure before coaching intelligence is designed. Future Sprint 5 work
can consume approved references only after governance, permissions, audit
events, and human review requirements are implemented and tested.

Until then, evidence packs remain passive containers for governed references.
