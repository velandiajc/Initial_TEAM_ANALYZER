# Evidence Artifact Framework

## Board-Approved Positioning

Sprint 4.1 Evidence Foundation Research is approved for planning and
implementation as pre-Sprint 5 foundation work. The framework creates governed
domain models for evidence traceability, review lifecycle, and evidence
packaging.

This is not Sprint 5 Coaching Intelligence. It does not make coaching decisions,
generate recommendations, process transcripts, parse recordings, or use AI.

## Sprint 4.1 Classification

Sprint 4.1 is an evidence governance foundation. Its outputs are domain models,
documentation, and structure-only templates that help TEAM_ANALYZER describe
evidence candidates before any production runtime feature is introduced.

Approved scope:

- Evidence discoverability.
- Evidence traceability.
- Evidence review lifecycle.
- Evidence packaging references.
- Tenant isolation fields.
- RBAC-ready ownership and review fields.
- Audit-event-ready lifecycle metadata.

## Evidence Discoverability vs Coaching Intelligence

Evidence discoverability answers whether a governed reference exists and whether
a human reviewer has accepted it for reference. Coaching Intelligence would
interpret performance, recommend actions, or produce coaching plans.

Sprint 4.1 stays on the discoverability side. It stores references and review
state only.

## Evidence Artifact Model

`EvidenceArtifact` represents metadata about a local or governed evidence
reference. It stores:

- `artifact_id`
- `tenant_id`
- `artifact_type`
- `source_reference`
- `linked_record_id`
- `discovered_at`
- `status`
- `reviewed_by`
- `reviewed_at`
- `lineage_id`
- `sensitivity`
- `processing_status`
- `metadata`

The artifact model is metadata-only. `source_reference` is a pointer or
reference, not embedded content. The model must not store audio, transcript
text, customer statements, PII, raw PDFs, raw recordings, or raw transcript
content.

## Evidence Link Candidate Model

`EvidenceLinkCandidate` represents a possible link between a source record and
an evidence reference. It stores:

- `candidate_id`
- `tenant_id`
- `source_record_id`
- `evidence_reference`
- `confidence_level`
- `confidence_score`
- `status`
- `created_at`
- `reviewed_by`
- `reviewed_at`
- `match_reason`
- `lineage_id`

Candidates default to `SUGGESTED`. A high confidence level never creates
automatic approval. Human review is required before a candidate can become an
approved evidence reference.

## Evidence Review Model

`EvidenceReview` captures human review traceability. It stores:

- `review_id`
- `tenant_id`
- `candidate_id`
- `artifact_id`
- `review_status`
- `reviewed_by`
- `reviewed_at`
- `review_notes`
- `lineage_id`

Review notes must remain summary-level governance notes. They must not include
raw customer content, transcript text, copied QA form content, or recording
content.

## Evidence Pack Model

`EvidencePack` is a passive container for reviewed evidence references,
supporting KPI references, and supporting Risk references. It stores:

- `evidence_pack_id`
- `tenant_id`
- `agent_id`
- `created_at`
- `review_status`
- `evidence_artifacts`
- `supporting_kpis`
- `supporting_risks`
- `notes`
- `sensitivity`
- `human_review_required`
- `root_cause_category`

The pack has no recommendation field, coaching score, AI summary, decision
field, or automated plan field. It prepares references for future human-reviewed
coaching workflows without implementing coaching behavior.

## Human Review Lifecycle

Candidate -> Human Review -> Approve -> Evidence Artifact

Candidate -> Human Review -> Reject

There is no automatic acceptance path. Suggested candidates remain suggestions
until a human reviewer records a review outcome.

## Tenant Isolation

Every evidence model includes `tenant_id`. Services and repositories introduced
in future work must treat tenant scope as mandatory and must reject cross-tenant
reads, writes, candidate links, reviews, and evidence packs.

## RBAC-Ready Design

Sprint 4.1 does not wire new runtime RBAC permissions. The models include fields
needed for future minimum-permission enforcement.

Recommended future permissions to document only:

- `view_evidence_candidate`
- `review_evidence_candidate`
- `view_evidence_artifact`

These permissions should be introduced only when a future service and test
surface can enforce them safely.

## Audit-Event-Ready Metadata

The models include lifecycle fields that can support future audit events:

- Creation timestamps.
- Review status.
- Reviewer identifiers.
- Review timestamps.
- Lineage identifiers.
- Processing status.
- Sensitivity classification.

Sprint 4.1 does not add audit event persistence or background audit jobs.

## Sensitivity Model

Evidence may be classified as:

- `INTERNAL`
- `CONFIDENTIAL`
- `RESTRICTED`

Recording evidence defaults to `RESTRICTED`. Evidence packs default to
`RESTRICTED` because even references, timing, and source identifiers can expose
sensitive operational context.

## Processing Status Model

Processing status values:

- `METADATA_ONLY`
- `REVIEW_REQUIRED`
- `HUMAN_REVIEW_REQUIRED`
- `APPROVED_FOR_REFERENCE`
- `REJECTED_FOR_REFERENCE`
- `ARCHIVED`

Default processing status is `METADATA_ONLY`. The model describes governance
state only and does not trigger processing.

## Prohibited Capabilities

Sprint 4.1 does not include:

- Speech-to-text.
- Transcription engines.
- Whisper.
- LLMs.
- OpenAI integration.
- Recommendations.
- Coaching automation.
- AI summaries.
- Background jobs.
- Schedulers.
- Queues.
- Automatic evidence approval.
- Raw recording storage.
- Raw transcript storage.
- Processing raw PDFs.
- Processing raw audio or video.
- Parsing MP4 files.
- Parsing transcript contents.
- Runtime dependencies on local evidence files.

## Relationship To KPI, Risk, And Future Coaching

KPI lineage can reference evidence artifacts only after future governance rules
approve an artifact for reference. Risk lineage can use reviewed evidence
references to explain supporting material without embedding raw content. Future
Coaching Intelligence can consume approved pack references after Sprint 5
designs the coaching layer.

This foundation does not change KPI calculations, Risk scoring, or coaching
behavior.

## Why This Is Not Sprint 5

Sprint 5 would introduce coaching intelligence behavior. Sprint 4.1 only defines
metadata models, review lifecycle, traceability vocabulary, and passive pack
structure. There are no coaching decisions, recommendations, AI summaries,
transcript processing, or automated plans.
