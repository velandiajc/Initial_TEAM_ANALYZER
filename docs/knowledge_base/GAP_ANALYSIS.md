# TEAM_ANALYZER Gap Analysis

## Overview

This gap analysis compares the repository implementation against:

- `AGENTS.md` mission and operating standards.
- `docs/frameworks/PMCE.md`.
- `docs/frameworks/QA_STANDARD.md`.
- `docs/frameworks/VOC_FRAMEWORK.md`.
- `docs/frameworks/COACHING_STANDARD.md`.

The repository has a strong foundation for survey ingestion, CSAT analysis, VOC sampling, agent discovery, and Markdown reporting. The biggest gap is that several mission areas exist as prompts, framework stubs, generic primitives, or standalone scripts rather than integrated product capabilities.

## Mission Alignment Summary

`AGENTS.md` defines TEAM_ANALYZER as a platform that transforms contact center operational data into:

- Actionable coaching.
- QA insights.
- CSAT analysis.
- VOC intelligence.
- Performance improvement plans.

Current implementation status:

| Mission Area | Status | Summary |
|---|---:|---|
| CSAT analysis | Implemented | Active survey pipeline calculates CSAT, classification, themes, and agent breakdowns. |
| VOC intelligence | Partial | VOC themes and samples exist, but structured root cause and controllability are not implemented. |
| QA insights | Partial | Standalone transcript QA script exists, but not integrated into active app or persistence. |
| Actionable coaching | Partial | Prompt and scripts generate coaching guidance, but there is no coaching entity, workflow, or follow-up tracking. |
| Performance improvement plans | Partial | Excel risk script creates leadership summaries, but no integrated scorecard or plan lifecycle exists. |

## What Is Already Implemented

### Active Survey Pipeline

Implemented through `main.py` and `app/services`:

- Cleanup of cache and generated outputs.
- Local folder creation for survey data, database, and reports.
- SQLite database initialization.
- Latest survey CSV discovery from `Data/raw/surveys`.
- CSV loading with pandas.
- Call/chat/unknown survey format detection.
- Survey normalization into canonical fields.
- Agent discovery from survey agent IDs and names.
- Agent alias generation and SQLite persistence.
- Survey persistence in SQLite.
- CSAT scaling to 0-100.
- Promoter, neutral, and detractor segmentation.
- VOC theme counting.
- Positive and negative VOC sample extraction.
- Agent-level survey breakdown.
- Markdown survey insights report export.
- PMCE interpretation prompt appended to the report.

### Data Models And Persistence

Implemented:

- `Agent` dataclass.
- `Survey` dataclass.
- SQLite `agents`, `agent_aliases`, and `surveys` tables.
- SQLite agent repository.
- SQLite survey repository.
- Agent alias lookup by ID, employee ID, name, nice name, CXone name, email, and alias.

### Survey Normalization Tests

Implemented in `tests/test_survey_normalizer.py`:

- Call survey normalization.
- Chat survey normalization.
- Missing optional columns.
- NaN comment cleanup.
- Chat comment fallback.
- OSAT vs CSAT score precedence.
- Numeric ID cleanup.

### Prompt-Based PMCE Interpretation

Implemented as a static prompt:

- `app/prompts/survey_insights_prompt.md` defines detailed PMCE, VOC, root cause, risk, agent coaching, process improvement, and next-action output expectations.
- The prompt is loaded and appended to `Reports/survey_insights.md`.

### Standalone Legacy Capabilities

Implemented as standalone scripts:

- `Scripts/transcribe_calls.py` transcribes call audio with faster-whisper.
- `Scripts/call_analyzer.py` performs keyword-based QA scoring and coaching summary generation from transcripts.
- `Scripts/risk_engine.py` performs Excel-based team performance, CSAT, DSAT, coaching, and risk analysis.
- `Scripts/parser.py`, `Scripts/find_performance.py`, and `Scripts/explorer.py` inspect a specific Markdown performance file.

## What Is Partially Implemented

### PMCE Framework

Framework definition:

- `docs/frameworks/PMCE.md` says PMCE is used to evaluate conversations, identify behaviors, and generate coaching recommendations.

Partial implementation:

- `survey_insights_prompt.md` contains a detailed PMCE interpretation framework.
- `Scripts/call_analyzer.py` includes QA sections that overlap with PMCE behaviors: greeting, acknowledging customer, service, documentation, wrap-up, empathy, ownership, verification, resolution, and closing.
- `app/core/Framework`, `Rule`, `Metric`, and `RulesEngine` could represent PMCE rules.

Gap:

- PMCE is not executable in the active pipeline.
- There is no PMCE score, PMCE observation model, PMCE ruleset, or PMCE repository.
- PMCE output exists only as prompt instruction or narrative script output.

### QA Standard

Framework definition:

- `docs/frameworks/QA_STANDARD.md` says it defines QA logic, scoring expectations, call monitoring standards, and audit notes structure.

Partial implementation:

- `Scripts/call_analyzer.py` has a hard-coded QA rubric with section weights and keyword checks.
- `QAResult` dataclass exists.
- `QARepository` exists as an in-memory dictionary.
- The prompt asks for QA calibration focus areas and QA evidence.

Gap:

- QA standard docs are not detailed enough to drive code.
- QA rubric is not configurable.
- QA script is not connected to active pipeline, database, or repositories.
- QA results are not persisted in SQLite.
- QA calibration workflow is missing.

### VOC Framework

Framework definition:

- `docs/frameworks/VOC_FRAMEWORK.md` says it defines sentiment, survey comments, detractors, root causes, and controllable vs non-controllable drivers.

Partial implementation:

- `SurveyInsightService` classifies promoters, neutrals, and detractors.
- `SurveyInsightService` detects VOC themes using hard-coded keywords.
- Positive and negative VOC samples are included in the generated report.
- The prompt requests controllability classification, root cause, and operational impact.

Gap:

- VOC framework doc is not executable or detailed.
- Theme detection is keyword-only and hard-coded.
- Root causes are not stored as structured data.
- Controllable vs non-controllable drivers are not calculated by code.
- No severity, owner, process, policy, or system classification exists in the active pipeline.

### Coaching Standard

Framework definition:

- `docs/frameworks/COACHING_STANDARD.md` says it defines coaching sessions, SMART commitments, performance recovery plans, and supervisor recommendations.

Partial implementation:

- `survey_insights_prompt.md` asks for PMCE coaching forms, root cause assessment, coaching focus, coaching notes, development actions, success indicators, and next actions.
- `Scripts/call_analyzer.py` generates coaching summaries from QA opportunities.
- `Scripts/risk_engine.py` calculates coaching focus, coaching needed, coaching action, coaching reason, and critical coaching flags.

Gap:

- There is no coaching session dataclass.
- There is no coaching repository or SQLite table.
- SMART commitments are not generated by code.
- Follow-up cadence and outcome tracking are not persisted.
- Supervisor recommendations are narrative only, not structured workflow items.

### Agent Analytics

Partial implementation:

- Agent discovery and aliasing are implemented.
- Agent-level survey breakdown is implemented.
- `SurveyAnalyticsService` can export agent survey summaries.
- `Scripts/risk_engine.py` calculates agent risk from Excel data.

Gap:

- No unified agent scorecard exists.
- Supervisor hierarchy is not active despite `Agent.supervisor` field.
- QA, survey, coaching, attendance, adherence, AUX, productivity, AHT, and sales metrics are not joined.
- No historical trends or performance improvement plan lifecycle exists.

### Generic Rule Framework

Partial implementation:

- `Framework`, `Metric`, `Observation`, `Rule`, `RuleResult`, and `RulesEngine` exist.

Gap:

- No active pipeline uses these classes.
- No framework rules are loaded from docs or configuration.
- Existing risk and QA logic is duplicated in scripts instead of represented as reusable rules.

## What Is Missing

### Missing Business Capabilities

| Capability | Why It Matters |
|---|---|
| Integrated call ingestion | Required to connect audio, transcripts, QA, VOC, and coaching. |
| Transcript persistence | Required for auditability and historical call analytics. |
| QA result persistence | Required to trend QA scores and join QA with CSAT and coaching. |
| Configurable QA rubric | Required to keep scoring aligned with `QA_STANDARD.md` without code changes. |
| Executable PMCE rules | Required to make PMCE more than a prompt narrative. |
| Structured VOC root cause model | Required to track controllability, process drivers, severity, and improvement ownership. |
| Coaching session lifecycle | Required for coaching accountability and follow-up. |
| SMART commitment generator | Required by `AGENTS.md` agent analysis format. |
| Performance recovery plans | Required to move from insight to action and ownership. |
| Unified agent scorecard | Required to support the primary metrics listed in `AGENTS.md`. |
| LLM execution layer | Required if AI interpretation should be generated directly by the app. |
| Data quality reporting | Required to explain invalid, missing, duplicate, or unmapped survey data. |

### Missing Technical Capabilities

| Capability | Why It Matters |
|---|---|
| Configuration layer | Paths, thresholds, keywords, report limits, and model settings are hard-coded. |
| SQLite migrations | Schema changes will be difficult to manage safely. |
| Service interfaces/protocols | Repository pattern is present but inconsistent. |
| End-to-end tests | Active pipeline behavior is not fully protected. |
| Script integration | Legacy scripts hold business logic outside the app architecture. |
| CI workflow | No automated verification is visible in the repo tree. |
| Prompt tests | Prompt behavior and report compatibility are not validated. |
| Structured output schemas | AI or report outputs cannot be reliably parsed or persisted. |

## Framework-by-Framework Gap Matrix

| Framework | Implemented | Partial | Missing |
|---|---|---|---|
| PMCE | Prompt describes PMCE dimensions in detail. | QA script overlaps with PMCE behaviors; generic rules engine could support PMCE. | PMCE scoring, PMCE observations, PMCE repository, and executable PMCE rules. |
| QA Standard | Standalone keyword QA scoring exists. | QA model and repository scaffolds exist. | Configurable QA rubric, persisted QA results, calibration, integrated QA pipeline. |
| VOC Framework | Survey sentiment and theme counts exist. | Prompt asks for root cause and controllability. | Structured VOC taxonomy, controllability classification, root cause persistence, severity/owner mapping. |
| Coaching Standard | Prompt asks for coaching forms and action plans. | Scripts generate coaching summaries and risk-based coaching actions. | Coaching sessions, SMART commitments, follow-ups, supervisor recommendations as structured records. |

## Operating Principles Gap Analysis

`AGENTS.md` lists operating principles. Current support:

| Operating Principle | Status | Evidence | Gap |
|---|---:|---|---|
| Performance-driven leadership | Partial | `risk_engine.py`, survey insights report | No integrated leadership dashboard or unified scorecard. |
| Root Cause Analysis | Partial | Prompt asks for RCA; VOC themes exist | RCA is not calculated or persisted by code. |
| Controllables vs Non-controllables | Partial | Prompt asks for classification | No executable controllability model. |
| Behavioral coaching | Partial | PMCE prompt and call analyzer summaries | No coaching workflow or SMART commitment persistence. |
| Accountability and ownership culture | Partial | Prompt tone and risk script actions | No owner/action tracking. |
| Continuous improvement | Partial | Reports and roadmap potential | No closed-loop improvement plan lifecycle. |

## Primary Metrics Gap Analysis

`AGENTS.md` lists primary metrics. Current support:

| Metric | Status | Evidence | Gap |
|---|---:|---|---|
| CSAT / OSAT | Implemented | Survey pipeline, insight service, tests | Trend and target analysis missing. |
| QA Score | Partial | `Scripts/call_analyzer.py` | Not integrated or persisted. |
| AHT | Missing | None | No model, loader, or report. |
| Adherence | Missing | Mentioned in `Observation` examples only | No ingestion or analytics. |
| Attendance | Missing | Mentioned in `Observation` examples only | No ingestion or analytics. |
| AUX usage | Missing | None | No ingestion or analytics. |
| Productivity | Missing | None | No ingestion or analytics. |
| Sales conversion / UPT | Partial | QA script has Sales/UPT rubric section | No operational sales metric ingestion or reporting. |

## Required Agent Analysis Format Gap

`AGENTS.md` requires agent analysis to include:

1. Coaching Session Summary.
2. Performance Strengths.
3. Areas of Improvement.
4. Root Cause Analysis.
5. Risk Assessment.
6. Recommended SMART Commitment.
7. Supervisor Strategic Recommendation.

Current status:

| Required Section | Status | Evidence | Gap |
|---|---:|---|---|
| Coaching Session Summary | Partial | Prompt and call analyzer coaching summary | Not generated as a formal agent artifact by active pipeline. |
| Performance Strengths | Partial | Prompt asks for strengths; promoter themes exist | Not explicitly generated per agent by code. |
| Areas of Improvement | Partial | Detractor themes and QA opportunities | Not unified per agent across data sources. |
| Root Cause Analysis | Partial | Prompt asks for RCA | Not computed or stored. |
| Risk Assessment | Partial | QA script and risk engine classify risk | No unified active risk model. |
| Recommended SMART Commitment | Missing | None | No SMART commitment generator. |
| Supervisor Strategic Recommendation | Partial | Prompt and script narratives | Not structured or persisted. |

## Technical Debt Impacting Mission Delivery

- `Scripts/` contains important business logic outside the active architecture.
- `project_structure.txt` is a very large generated file committed to the repo.
- Several scaffold files make implementation status ambiguous.
- Framework docs are intent statements rather than executable standards.
- Business rules are spread across hard-coded dictionaries, scripts, prompts, and docs.
- SQLite schema only covers survey and agent data.
- No migrations or configuration layer exist.
- `SurveyInsightService` owns too many responsibilities.
- Tests are concentrated on survey normalization only.

## Recommended Gap Closure Roadmap

### Step 1: Close Survey Pipeline Gaps

- Add end-to-end survey pipeline tests.
- Add structured data validation and ingestion diagnostics.
- Move VOC keywords and CSAT thresholds into configuration.
- Split analytics and report rendering responsibilities.

### Step 2: Make Frameworks Operational

- Convert PMCE, QA, VOC, and coaching standards into structured config or executable rules.
- Wire `RulesEngine` into survey, QA, and risk analysis.
- Add framework tests and example rules.

### Step 3: Integrate QA And Calls

- Move call transcription and QA scoring into `app/services`.
- Implement `call_ingestion_service.py`.
- Add SQLite tables and repositories for calls, transcripts, and QA results.
- Replace hard-coded script paths with configuration.

### Step 4: Build Coaching Workflow

- Add coaching session, coaching recommendation, SMART commitment, and follow-up models.
- Persist coaching outputs and supervisor actions.
- Generate the required `AGENTS.md` agent analysis format from combined survey, QA, VOC, and risk signals.

### Step 5: Build Performance Improvement Plans

- Add agent scorecards across CSAT, QA, AHT, adherence, attendance, AUX, productivity, and sales metrics.
- Convert risk logic into reusable rules.
- Add performance recovery plans with owner, due date, metric target, and status.

### Step 6: Add AI Execution And Governance

- Add an LLM execution service for prompt-based interpretation.
- Add structured output schemas for generated coaching and executive recommendations.
- Add prompt tests and versioning.
- Store AI-generated analysis separately from raw reports for review and auditability.

## Conclusion

TEAM_ANALYZER already has a practical survey analytics core and a clear contact center operations mission. The repository's strongest implemented area is survey-based CSAT and VOC reporting. Its strongest untapped assets are the standalone QA, transcription, and risk scripts plus the generic rule framework.

The main work ahead is integration: convert framework intent, prompts, and scripts into structured services, repositories, rules, tests, and persisted business workflows. Once that is done, the project can move from report generation toward a full operational coaching and performance improvement platform.
