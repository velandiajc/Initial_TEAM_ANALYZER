# Evidence Dataset Assessment

## Purpose

The Evidence Dataset Assessment workflow is a local-only discovery utility for
understanding whether uploaded QA audit PDFs and CXone recording MP4s can support
future operational lineage work in TEAM_ANALYZER.

This workflow is not a product feature, not Sprint 5 scope, and not a runtime
dependency. It exists to create a metadata-only inventory that can inform data
governance decisions before any sensitive evidence content is processed.

## Why Raw Evidence Is Outside Git

Raw QA audit PDFs and call recordings can contain restricted information,
including customer statements, agent identifiers, phone numbers, account
references, internal QA commentary, and call audio. These files must remain local
and must not be committed to Git.

The project ignore rules exclude:

- `data/raw/evidence_samples/`
- `data/processed/evidence/`
- `*.mp4`
- `*.wav`
- `*.mp3`
- `*.pdf`

The workflow stores only generated metadata in local processed folders. Those
generated outputs are also outside Git because even metadata can reveal sensitive
operational patterns.

## How Evidence Can Support Lineage

Evidence files may eventually help connect operational metrics to governance and
coaching workflows, but only after KPI, Risk, and Coaching foundations are
consolidated.

Potential lineage value:

- QA KPI lineage: audit filenames can identify whether QA evidence exists for an
  agent, month, or week before any QA score is trusted as governed source data.
- Risk Result lineage: recording and audit availability can help explain whether
  a risk result has supporting evidence, missing evidence, or source-system gaps.
- Future Coaching Evidence Packs: once governance and privacy controls mature,
  approved metadata could help assemble evidence references for supervisor review
  without copying raw content into coaching outputs.

This assessment does not calculate KPIs, alter risk scoring, or generate coaching
recommendations.

## Privacy And PII Risks

The evidence dataset should be treated as restricted. Risks include:

- Customer PII in audio, PDFs, filenames, or QA comments.
- Employee PII in filenames, audit forms, and source-system exports.
- Sensitive operational details such as interaction UUIDs, call timing, QA
  disputes, escalation content, or compliance observations.
- Accidental persistence of raw call content in Markdown, CSV, logs, tests, or
  Git history.

The current workflow reduces risk by scanning only filenames, file extensions,
file sizes, and local paths. It does not open PDFs for text extraction and does
not decode or transcribe audio/video files.

## Why Audio Transcription Is Deferred

Audio transcription is intentionally deferred because it would process sensitive
call content and create new derived records that may contain PII, protected
customer information, and regulated interaction details. Before transcription is
considered, TEAM_ANALYZER needs stronger controls for consent, retention,
redaction, access permissions, audit logging, source ownership, and quality
review.

## Why Operational AI Is Deferred

Operational AI is deferred because the project audit recommended consolidating
KPI, Risk, Coaching, governance, and documentation foundations before major
feature expansion. AI-generated QA insights, speech analytics, coaching
automation, recommendations, and dashboards would create high-impact behavior
from data that is not yet governed enough for automated action.

The current workflow supports readiness assessment only.

## Recommended Future Architecture

A future production architecture should keep evidence handling separate from the
runtime product path:

1. Secure evidence store outside Git with explicit retention and access policy.
2. Metadata catalog that stores source-system references, file hashes, periods,
   agent identifiers, and processing status.
3. Governance gate for source eligibility before evidence can support KPI or risk
   results.
4. PII detection and redaction pipeline before any content-derived artifact is
   stored.
5. Human review queue for QA and compliance validation.
6. Evidence reference layer that links coaching packs to governed evidence IDs,
   not raw PDFs, audio, or transcripts.
7. Audit trail for every evidence processing step.

## Manifest Schema

The local manifest is generated at:

`data/processed/evidence/manifest/qa_evidence_manifest.csv`

Fields:

- `file_name`: Original local filename.
- `file_type`: File extension without the dot, currently `pdf` or `mp4`.
- `evidence_type`: `qa_audit` for PDFs or `recording` for MP4s.
- `agent_name`: Agent name inferred from filename tokens, or `unknown`.
- `month`: Month inferred from filename or recording date, or `unknown`.
- `week_number`: Week number inferred from `week` or `wk` filename tokens, or
  `unknown`.
- `recording_date`: Date inferred from filename in `YYYY-MM-DD` format, or
  `unknown`.
- `recording_time_utc`: Time inferred from filename in `HH:MM:SS` format, or
  `unknown`.
- `source_system`: Source inferred from filename and type, currently `cxone` or
  `qa_audit`.
- `source_uuid`: UUID found in filename, or `unknown`.
- `file_size_bytes`: Local file size from filesystem metadata.
- `local_file_reference`: Local path reference for human assessment.
- `sensitivity`: Always `restricted`.
- `processing_status`: Always `metadata_only`.

The companion Markdown files are generated under:

- `data/processed/evidence/markdown/audits/`
- `data/processed/evidence/markdown/recordings/`

Each Markdown file repeats manifest metadata only and must not contain raw PDF
text, call audio text, transcripts, QA comments, or customer statements.

## Out Of Scope

This workflow does not:

- Commit raw PDFs, MP4s, WAVs, MP3s, or generated evidence outputs.
- Extract PDF text.
- Decode audio or video.
- Transcribe calls.
- Call external AI services.
- Generate QA insights, speech analytics, coaching recommendations, or
  dashboards.
- Modify source data files directly.
- Create runtime application dependencies on local historical files.
- Change KPI calculations, risk scoring, or coaching workflows.
