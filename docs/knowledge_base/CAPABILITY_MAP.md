# TEAM_ANALYZER Capability Map

## Overview

This map analyzes the Python codebase by business capability. Capability status is defined as:

- Implemented: executable code is wired into the active pipeline or can run as a complete standalone utility.
- Partial: meaningful code exists, but it is incomplete, disconnected, hard-coded, or not integrated into the main pipeline.
- Scaffolded: file, class, or model exists but provides little or no executable business behavior.
- Missing: capability is required by the mission or framework but is not represented by implementation.

The active production-like path is `main.py` plus the `app/services` survey pipeline. The `Scripts/` folder contains additional standalone capabilities that are valuable but not integrated into the active application architecture.

## Python File Inventory

| File | Primary Role | Status | Capability Notes |
|---|---|---:|---|
| `main.py` | Async batch pipeline orchestration | Implemented | Runs cleanup, folder setup, database initialization, CSV discovery, survey loading, agent discovery, survey persistence, insight generation, and Markdown export. |
| `Analyze_team.py` | Placeholder | Scaffolded | Empty file. |
| `coaching_generator.py` | Placeholder | Scaffolded | Empty file. |
| `Scripts/transcribe_calls.py` | Call transcription | Partial | Transcribes `.mp4` files with faster-whisper using hard-coded folders. Standalone only. |
| `Scripts/call_analyzer.py` | Keyword QA scoring and coaching notes | Partial | Generates QA score, risk level, auditor notes, coaching summary, Markdown, and JSON from transcripts. Not integrated into `app/`. |
| `Scripts/risk_engine.py` | Excel-based team risk and coaching analysis | Partial | Loads roaster, CSAT, DSAT, and coaching sheets; exports combined analysis and leadership summary. Hard-coded workbook structure and standalone runtime. |
| `Scripts/parser.py` | Markdown exploration | Partial | Extracts sections and searches operational keywords in one hard-coded Markdown file. |
| `Scripts/find_performance.py` | Markdown performance search | Partial | Searches performance keywords in one hard-coded Markdown file. |
| `Scripts/explorer.py` | Team performance section explorer | Partial | Searches one hard-coded Markdown file for team performance overview. |
| `app/core/__init__.py` | Generic entity model | Scaffolded | Defines `Entity` but it is not used by the active pipeline. |
| `app/core/entity.py` | Placeholder | Scaffolded | Empty file. |
| `app/core/framework.py` | Framework model | Partial | Supports rules and metadata, but no production framework definitions are loaded into runtime. |
| `app/core/metric.py` | Metric model | Partial | Supports target comparison and variance, but not wired into active analytics. |
| `app/core/observation.py` | Observation model | Partial | Generic observation model for surveys, QA, attendance, calls, transcripts, coaching; not used by runtime. |
| `app/core/rule.py` | Rule and rule result model | Partial | Implements threshold comparisons, but no active business rules use it. |
| `app/engines/rules_engine.py` | Framework rules evaluation | Partial | Evaluates metrics against framework rules; not connected to survey, QA, or risk pipeline. |
| `app/models/agent.py` | Agent dataclass | Implemented | Used by `AgentRegistry` and agent identity logic. |
| `app/models/survey.py` | Survey dataclass | Implemented | Used by `SurveyLoader`, repositories, and insight services. |
| `app/models/call.py` | Call dataclass | Scaffolded | Represents calls but is not connected to ingestion or persistence. |
| `app/models/qa_result.py` | QA result dataclass | Scaffolded | Represents QA result fields but is not connected to scoring or persistence. |
| `app/models/transcript.py` | Transcript dataclass | Scaffolded | Represents transcript metadata but is not connected to transcription or persistence. |
| `app/services/cleanup_service.py` | Runtime cleanup | Implemented | Cleans caches and generated output folders. |
| `app/services/database_service.py` | SQLite schema and connection | Implemented | Creates `agents`, `agent_aliases`, and `surveys` tables. |
| `app/services/agent_registry.py` | In-memory agent identity lookup | Partial | Supports rich lookup and JSON loading. In active pipeline it is instantiated empty. |
| `app/services/agent_discovery_service.py` | JSON master-file discovery | Partial | Discovers agents into JSON master file. Mostly superseded by SQLite discovery. |
| `app/services/sqlite_agent_discovery_service.py` | SQLite-backed agent discovery | Implemented | Discovers and upserts agents and aliases from survey rows. |
| `app/services/sqlite_agent_repository.py` | SQLite agent repository | Implemented | Upserts agents and resolves IDs by identity or alias. |
| `app/services/sqlite_survey_repository.py` | SQLite survey repository | Implemented | Upserts surveys and returns raw survey rows. |
| `app/services/survey_repository.py` | In-memory survey repository | Partial | Useful as a simple repository but not active in runtime. |
| `app/services/call_repository.py` | In-memory call repository | Scaffolded | Basic add/get/get-by-agent only; not active. |
| `app/services/qa_repository.py` | In-memory QA repository | Scaffolded | Basic add/get only; not active. |
| `app/services/transcript_repository.py` | In-memory transcript repository | Scaffolded | Basic add/get only; not active. |
| `app/services/call_ingestion_service.py` | Placeholder | Scaffolded | Empty file. |
| `app/services/survey_loader.py` | CSV-to-survey loader | Implemented | Reads CSV with pandas, normalizes rows, maps agent IDs, creates `Survey` objects. |
| `app/services/survey_normalizer.py` | Survey schema normalization | Implemented | Detects call/chat/unknown formats and normalizes fields. |
| `app/services/survey_analytics_service.py` | Agent survey summaries | Partial | Builds and exports agent survey summaries but is not used by `main.py`. |
| `app/services/survey_insight_service.py` | CSAT, VOC, and report generation | Implemented | Builds insight dictionaries and exports survey insight Markdown with PMCE prompt. |
| `app/utils/file_finder.py` | Latest file discovery | Implemented | Finds latest CSV or Excel file by modification time. |
| `tests/test_survey_normalizer.py` | Survey normalization tests | Implemented | Tests call/chat normalization, fallback behavior, missing values, score precedence, and numeric ID cleanup. |

## Customer Experience Capabilities

| Capability | Status | Evidence | Notes |
|---|---:|---|---|
| CSAT/OSAT ingestion | Implemented | `SurveyLoader`, `SurveyNormalizer`, `SQLiteSurveyRepository` | Supports call and chat survey exports. |
| Customer feedback capture | Implemented | `Survey.comment`, `SurveyInsightService._clean_comment` | Captures survey comment text and uses it in VOC samples. |
| Customer sentiment segmentation | Implemented | `SurveyInsightService._classify` | Segments into promoter, neutral, and detractor using CSAT scaled to 0-100. |
| Customer pain point themes | Implemented | `SurveyInsightService._detect_theme` | Uses keyword themes for shipping, returns, agent service, resolution, policy/promo, website/system, product/order, and communication. |
| Customer user story generation | Partial | `SurveyInsightService.export_markdown_report` | Static user stories are generated; they are not dynamically derived from actual themes. |
| Customer effort and first contact resolution analysis | Missing | Mission and prompt mention effort/FCR | No structured FCR or repeat-contact metric exists. |
| Executive CX health summary | Partial | `SurveyInsightService.export_markdown_report`, prompt | Report includes metrics; richer executive interpretation depends on external prompt usage. |

## QA Capabilities

| Capability | Status | Evidence | Notes |
|---|---:|---|---|
| QA result model | Scaffolded | `app/models/qa_result.py` | Dataclass exists but is not used. |
| QA repository | Scaffolded | `app/services/qa_repository.py` | In-memory add/get only. |
| Keyword-based call QA scoring | Partial | `Scripts/call_analyzer.py` | Standalone script scores transcript text against hard-coded rubric sections. |
| QA risk level classification | Partial | `Scripts/call_analyzer.py` | Converts QA score to Low, Moderate, High, or Critical risk. |
| QA auditor notes | Partial | `Scripts/call_analyzer.py` | Generates scripted auditor notes and copy/paste form notes. |
| QA standard integration | Missing | `docs/frameworks/QA_STANDARD.md` | Framework doc exists but does not drive scoring logic. |
| QA persistence | Missing | `DatabaseService` has no QA tables | No persisted QA result pipeline. |
| QA calibration analytics | Missing | Mission/prompt mention calibration | No calibration model, workflow, or report exists. |

## VOC Capabilities

| Capability | Status | Evidence | Notes |
|---|---:|---|---|
| VOC sample extraction | Implemented | `SurveyInsightService` | Positive and negative comments are extracted from promoters/detractors. |
| VOC theme detection | Implemented | `_detect_theme` | Uses hard-coded keyword mapping. |
| Promoter drivers | Implemented | `promoter_themes` | Counts themes from promoter surveys. |
| Detractor drivers | Implemented | `detractor_themes` | Counts themes from detractor surveys. |
| Top VOC themes | Implemented | `theme_counter` | Aggregates all detected themes. |
| Controllable vs non-controllable classification | Partial | `AGENTS.md`, prompt, `Scripts/risk_engine.py` | Prompt asks for classification; code has DSAT/risk logic but no structured VOC taxonomy. |
| VOC framework execution | Missing | `docs/frameworks/VOC_FRAMEWORK.md` | Framework doc is intent-only and not machine-readable. |
| Root cause taxonomy persistence | Missing | Mission and prompt | Root causes are not stored as structured records. |

## Coaching Capabilities

| Capability | Status | Evidence | Notes |
|---|---:|---|---|
| PMCE coaching prompt | Implemented | `app/prompts/survey_insights_prompt.md` | Detailed PMCE coaching instructions exist. |
| Coaching summary from QA script | Partial | `Scripts/call_analyzer.py` | Generates coaching summary from QA opportunities. |
| Coaching need calculation | Partial | `Scripts/risk_engine.py` | Calculates coaching needed, focus, action, reason, and critical flag from Excel data. |
| SMART commitment generation | Missing | `AGENTS.md` | Required format mentions SMART commitment, but no executable generator exists. |
| Coaching session model | Missing | No dataclass/table | No structured coaching session entity. |
| Coaching follow-up persistence | Missing | No repository/table | Excel script reads follow-up sheets but active app does not persist coaching records. |
| Supervisor strategic recommendation | Partial | Prompt and script summaries | Generated as narrative, not as structured workflow. |
| PMCE framework scoring | Missing | `docs/frameworks/PMCE.md` | PMCE is prompt text and framework doc intent, not executable code. |

## Survey Analytics Capabilities

| Capability | Status | Evidence | Notes |
|---|---:|---|---|
| Latest survey file discovery | Implemented | `FileFinder.latest_csv` | Selects latest CSV by modified time. |
| Survey type detection | Implemented | `SurveyNormalizer.detect_survey_type` | Detects chat, call, or unknown. |
| Call survey normalization | Implemented | `_normalize_call_row` and tests | Handles `contactid`, `agentno`, `agentname`, `OSAT`, comments, reasons, dispositions. |
| Chat survey normalization | Implemented | `_normalize_chat_row` and tests | Handles `chat id`, `ano`/`icano`, `afn`, `CSAT`, comments. |
| Unknown survey fallback | Implemented | `_normalize_unknown_row` | Provides fallback mapping for mixed/unknown files. |
| Survey persistence | Implemented | `SQLiteSurveyRepository` | Upserts by `contact_id`. |
| CSAT overview report | Implemented | `SurveyInsightService.export_markdown_report` | Total, average CSAT, promoters, neutrals, detractors. |
| Agent survey summary export | Partial | `SurveyAnalyticsService` | Exports CSV but not wired into `main.py`. |
| Survey data validation | Missing | No validation layer | Missing required-column checks, schema errors, duplicate diagnostics, and quality report. |

## Agent Analytics Capabilities

| Capability | Status | Evidence | Notes |
|---|---:|---|---|
| Agent discovery from surveys | Implemented | `SQLiteAgentDiscoveryService` | Creates/updates agents from agent ID and name. |
| Agent aliasing | Implemented | `SQLiteAgentDiscoveryService`, `SQLiteAgentRepository`, `AgentRegistry` | Supports numeric, original, proper-name, and accent-normalized aliases. |
| Agent-level survey breakdown | Implemented | `SurveyInsightService.agent_breakdown` | Surveys, average CSAT, promoters, neutrals, detractors. |
| Agent survey CSV summary | Partial | `SurveyAnalyticsService` | Available but not called by active pipeline. |
| Agent performance risk | Partial | `Scripts/risk_engine.py` | Calculates risk from Excel inputs but is disconnected from active app. |
| Agent QA performance | Partial | `Scripts/call_analyzer.py` and `QAResult` | Per-call QA exists in script; not persisted or joined to survey analytics. |
| Agent scorecard | Missing | Mission metrics | No unified agent scorecard across CSAT, QA, AHT, adherence, attendance, AUX, productivity, sales conversion, and UPT. |
| Supervisor/team hierarchy analytics | Missing | `Agent.supervisor` field exists | Supervisor field exists but is empty/disconnected; no hierarchy reporting. |

## Capability Gaps By Mission Area

| Mission Area | Current State | Highest-Impact Gap |
|---|---|---|
| Customer Experience | Strong survey/VOC baseline | No FCR, customer effort, repeat-contact, or process-owner model. |
| QA Insights | Standalone transcript QA script | No integrated QA service, persisted QA results, or configurable QA standard. |
| CSAT Analysis | Active and tested survey normalization plus insight report | Thresholds and themes are hard-coded; limited validation and no trend analytics. |
| VOC Intelligence | Keyword theme detection and VOC samples | No structured root cause, controllability, severity, or action-owner classification. |
| Coaching | Prompt and script-generated coaching notes | No coaching session lifecycle, SMART commitment entity, or follow-up tracking. |
| Performance Improvement Plans | Excel risk script has useful logic | No integrated performance scorecard or roadmap from risk to action tracking. |

## Recommended Capability Priorities

1. Stabilize survey analytics as the source of truth for CSAT and VOC.
2. Move QA transcription and QA scoring scripts into `app/services/` with configurable paths and repositories.
3. Convert framework docs into executable rules or structured configs.
4. Add coaching session and SMART commitment models.
5. Create a unified agent performance scorecard that joins survey, QA, coaching, and operational metrics.
6. Add end-to-end tests covering survey ingestion, agent discovery, persistence, and report generation.
