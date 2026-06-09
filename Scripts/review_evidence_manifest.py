from __future__ import annotations

import argparse
import calendar
import csv
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path


DEFAULT_MANIFEST_PATH = Path(
    "data/processed/evidence/manifest/qa_evidence_manifest.csv"
)
DEFAULT_REVIEW_ROOT = Path("data/processed/evidence/review")

LINK_CANDIDATE_FIELDS = [
    "agent_name",
    "audit_file_name",
    "audit_week_number",
    "audit_month",
    "recording_file_name",
    "recording_date",
    "recording_time_utc",
    "match_reason",
    "match_confidence",
]

EXPECTED_MANIFEST_FIELDS = [
    "file_name",
    "file_type",
    "evidence_type",
    "agent_name",
    "month",
    "week_number",
    "recording_date",
    "recording_time_utc",
    "source_system",
    "source_uuid",
    "file_size_bytes",
    "local_file_reference",
    "sensitivity",
    "processing_status",
]

UNKNOWN_VALUES = {"", "unknown", "none", "null", "n/a", "na"}
HEX_FRAGMENT_PATTERN = re.compile(r"^[0-9a-f]{3,}$", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"^\d+$")

MONTH_NAME_TO_NUMBER = {
    month_name.lower(): index
    for index, month_name in enumerate(calendar.month_name)
    if month_name
}
MONTH_ABBR_TO_NUMBER = {
    month_name.lower(): index
    for index, month_name in enumerate(calendar.month_abbr)
    if month_name
}


def read_manifest(manifest_path: Path = DEFAULT_MANIFEST_PATH) -> list[dict[str, str]]:
    if not manifest_path.exists():
        return []

    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        reader = csv.DictReader(manifest_file)
        return [
            normalize_row(row)
            for row in reader
        ]


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = {}
    for field in EXPECTED_MANIFEST_FIELDS:
        normalized[field] = (row.get(field) or "").strip()
    return normalized


def build_review(rows: list[dict[str, str]]) -> dict[str, object]:
    inventory = build_inventory(rows)
    agent_coverage = build_agent_coverage(rows)
    period_coverage = build_period_coverage(rows)
    data_quality = build_data_quality(rows)
    link_candidates = build_link_candidates(rows)

    return {
        "rows": rows,
        "inventory": inventory,
        "agent_coverage": agent_coverage,
        "period_coverage": period_coverage,
        "data_quality": data_quality,
        "link_candidates": link_candidates,
    }


def build_inventory(rows: list[dict[str, str]]) -> dict[str, object]:
    return {
        "total_evidence_files": len(rows),
        "count_by_evidence_type": count_values(rows, "evidence_type"),
        "count_by_file_type": count_values(rows, "file_type"),
        "count_by_sensitivity": count_values(rows, "sensitivity"),
        "count_by_processing_status": count_values(rows, "processing_status"),
    }


def build_agent_coverage(rows: list[dict[str, str]]) -> dict[str, object]:
    agent_rows = [
        row
        for row in rows
        if not is_missing(row.get("agent_name"))
    ]
    normalized_agents = {
        normalize_agent_name(row["agent_name"])
        for row in agent_rows
        if normalize_agent_name(row["agent_name"])
    }

    evidence_by_agent = Counter()
    audit_by_agent = Counter()
    recording_by_agent = Counter()
    display_names = {}

    for row in agent_rows:
        normalized_agent = normalize_agent_name(row["agent_name"])
        if not normalized_agent:
            continue

        display_names.setdefault(normalized_agent, clean_display_agent_name(row["agent_name"]))
        evidence_by_agent[normalized_agent] += 1
        if is_audit(row):
            audit_by_agent[normalized_agent] += 1
        if is_recording(row):
            recording_by_agent[normalized_agent] += 1

    agent_summary = []
    for normalized_agent in sorted(evidence_by_agent):
        agent_summary.append(
            {
                "agent_name": display_names[normalized_agent],
                "evidence_count": evidence_by_agent[normalized_agent],
                "audit_count": audit_by_agent[normalized_agent],
                "recording_count": recording_by_agent[normalized_agent],
            }
        )

    top_agents = sorted(
        agent_summary,
        key=lambda item: (-item["evidence_count"], item["agent_name"].lower()),
    )[:20]

    audits_without_recordings = [
        item["agent_name"]
        for item in agent_summary
        if item["audit_count"] > 0 and item["recording_count"] == 0
    ]
    recordings_without_audits = [
        item["agent_name"]
        for item in agent_summary
        if item["recording_count"] > 0 and item["audit_count"] == 0
    ]

    return {
        "distinct_agents": len(normalized_agents),
        "evidence_count_per_agent": agent_summary,
        "audit_count_per_agent": {
            item["agent_name"]: item["audit_count"]
            for item in agent_summary
        },
        "recording_count_per_agent": {
            item["agent_name"]: item["recording_count"]
            for item in agent_summary
        },
        "top_20_agents_by_evidence_count": top_agents,
        "agents_with_audit_pdfs_but_no_recordings": audits_without_recordings,
        "agents_with_recordings_but_no_audit_pdfs": recordings_without_audits,
    }


def build_period_coverage(rows: list[dict[str, str]]) -> dict[str, Counter]:
    rows_with_dates = [
        row
        for row in rows
        if not is_missing(row.get("recording_date"))
    ]
    return {
        "count_by_month": count_values(rows, "month"),
        "count_by_week_number": count_values(rows, "week_number"),
        "count_by_recording_date": count_values(rows_with_dates, "recording_date"),
    }


def build_data_quality(rows: list[dict[str, str]]) -> dict[str, object]:
    file_name_counts = Counter(row["file_name"] for row in rows if row["file_name"])
    duplicate_file_names = {
        file_name: count
        for file_name, count in sorted(file_name_counts.items())
        if count > 1
    }

    missing_agent_name = [row for row in rows if is_missing(row.get("agent_name"))]
    missing_evidence_type = [row for row in rows if is_missing(row.get("evidence_type"))]
    missing_week_number_for_audits = [
        row
        for row in rows
        if is_audit(row) and is_missing(row.get("week_number"))
    ]
    missing_recording_date_for_recordings = [
        row
        for row in rows
        if is_recording(row) and is_missing(row.get("recording_date"))
    ]
    unknown_filename_pattern = [
        row
        for row in rows
        if is_unknown_filename_pattern(row)
    ]
    files_without_parsed_metadata = [
        row
        for row in rows
        if has_no_parsed_metadata(row)
    ]

    return {
        "missing_agent_name": len(missing_agent_name),
        "missing_evidence_type": len(missing_evidence_type),
        "missing_week_number_for_audit_pdfs": len(missing_week_number_for_audits),
        "missing_recording_date_for_mp4_recordings": len(
            missing_recording_date_for_recordings
        ),
        "duplicate_file_name": sum(duplicate_file_names.values()),
        "duplicate_file_names": duplicate_file_names,
        "unknown_filename_pattern": len(unknown_filename_pattern),
        "files_without_parsed_metadata": len(files_without_parsed_metadata),
    }


def build_link_candidates(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    audits = [row for row in rows if is_audit(row)]
    recordings = [row for row in rows if is_recording(row)]
    candidates = []

    recordings_by_agent = defaultdict(list)
    for recording in recordings:
        normalized_agent = normalize_agent_name(recording.get("agent_name", ""))
        if normalized_agent:
            recordings_by_agent[normalized_agent].append(recording)

    for audit in audits:
        normalized_agent = normalize_agent_name(audit.get("agent_name", ""))
        if not normalized_agent:
            continue

        for recording in recordings_by_agent.get(normalized_agent, []):
            match = classify_match(audit, recording)
            if not match:
                continue

            candidates.append(
                {
                    "agent_name": clean_display_agent_name(audit.get("agent_name", "")),
                    "audit_file_name": audit.get("file_name", ""),
                    "audit_week_number": value_or_unknown(audit.get("week_number")),
                    "audit_month": value_or_unknown(audit.get("month")),
                    "recording_file_name": recording.get("file_name", ""),
                    "recording_date": value_or_unknown(recording.get("recording_date")),
                    "recording_time_utc": value_or_unknown(
                        recording.get("recording_time_utc")
                    ),
                    "match_reason": match["reason"],
                    "match_confidence": match["confidence"],
                }
            )

    return sorted(
        candidates,
        key=lambda item: (
            item["agent_name"].lower(),
            item["audit_file_name"].lower(),
            item["match_confidence"],
            item["recording_date"],
            item["recording_file_name"].lower(),
        ),
    )


def classify_match(audit: dict[str, str], recording: dict[str, str]) -> dict[str, str] | None:
    month_match = months_match(audit.get("month", ""), recording.get("month", ""))
    week_match = weeks_match(audit.get("week_number", ""), recording.get("week_number", ""))
    date_in_week_range = recording_date_in_audit_week(audit, recording)

    if month_match and (week_match or date_in_week_range):
        return {
            "reason": "same normalized agent, same month, and matching audit week range",
            "confidence": "high",
        }

    if month_match:
        return {
            "reason": "same normalized agent and same month",
            "confidence": "medium",
        }

    if date_in_week_range:
        return {
            "reason": "same normalized agent and recording date falls in audit week range",
            "confidence": "medium",
        }

    if not is_missing(audit.get("month")) or not is_missing(audit.get("week_number")):
        return {
            "reason": "same normalized agent; period metadata is incomplete or not aligned",
            "confidence": "low",
        }

    return None


def write_review_outputs(
    review: dict[str, object],
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> dict[str, Path]:
    review_root.mkdir(parents=True, exist_ok=True)

    summary_path = review_root / "evidence_dataset_summary.md"
    quality_path = review_root / "evidence_quality_report.md"
    candidates_path = review_root / "evidence_link_candidates.csv"

    summary_path.write_text(render_dataset_summary(review), encoding="utf-8")
    quality_path.write_text(render_quality_report(review), encoding="utf-8")
    write_link_candidates(
        review["link_candidates"],
        candidates_path,
    )

    return {
        "summary": summary_path,
        "quality_report": quality_path,
        "link_candidates": candidates_path,
    }


def write_link_candidates(candidates: list[dict[str, str]], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as candidates_file:
        writer = csv.DictWriter(candidates_file, fieldnames=LINK_CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerows(candidates)


def review_evidence_manifest(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> tuple[dict[str, object], dict[str, Path]]:
    rows = read_manifest(manifest_path)
    review = build_review(rows)
    output_paths = write_review_outputs(review, review_root)
    return review, output_paths


def render_dataset_summary(review: dict[str, object]) -> str:
    inventory = review["inventory"]
    agent_coverage = review["agent_coverage"]
    period_coverage = review["period_coverage"]
    link_candidates = review["link_candidates"]

    total = inventory["total_evidence_files"]
    distinct_agents = agent_coverage["distinct_agents"]
    candidate_count = len(link_candidates)

    lines = [
        "# Evidence Dataset Summary",
        "",
        "This local review uses manifest metadata only. It does not read PDF text,",
        "decode audio/video, transcribe calls, use AI, or process raw call content.",
        "",
        "## Dataset Value Assessment",
        "",
        dataset_value_assessment(total, distinct_agents, candidate_count),
        "",
        "## Inventory",
        "",
        f"- Total evidence files: {total}",
        "",
        "### Count By Evidence Type",
        "",
        render_counter_table(inventory["count_by_evidence_type"], "Evidence type"),
        "",
        "### Count By File Type",
        "",
        render_counter_table(inventory["count_by_file_type"], "File type"),
        "",
        "### Count By Sensitivity",
        "",
        render_counter_table(inventory["count_by_sensitivity"], "Sensitivity"),
        "",
        "### Count By Processing Status",
        "",
        render_counter_table(
            inventory["count_by_processing_status"],
            "Processing status",
        ),
        "",
        "## Agent Coverage",
        "",
        f"- Distinct agents: {distinct_agents}",
        f"- Agents with audit PDFs but no recordings: "
        f"{len(agent_coverage['agents_with_audit_pdfs_but_no_recordings'])}",
        f"- Agents with recordings but no audit PDFs: "
        f"{len(agent_coverage['agents_with_recordings_but_no_audit_pdfs'])}",
        "",
        "### Top 20 Agents By Evidence Count",
        "",
        render_agent_table(agent_coverage["top_20_agents_by_evidence_count"]),
        "",
        "## Period Coverage",
        "",
        "### Count By Month",
        "",
        render_counter_table(period_coverage["count_by_month"], "Month"),
        "",
        "### Count By Week Number",
        "",
        render_counter_table(period_coverage["count_by_week_number"], "Week number"),
        "",
        "### Count By Recording Date",
        "",
        render_counter_table(
            period_coverage["count_by_recording_date"],
            "Recording date",
            limit=30,
        ),
        "",
        "## Future Lineage Support",
        "",
        "QA KPI lineage: the manifest can show whether an agent, month, and week",
        "have local QA audit evidence before those records are considered governed",
        "KPI inputs.",
        "",
        "Risk Result lineage: evidence availability can help separate performance",
        "signals with supporting operational evidence from signals with source gaps",
        "or missing review artifacts.",
        "",
        "Coaching Evidence Packs: candidate links can later inform human-reviewed",
        "evidence references, but this utility does not generate coaching content",
        "or recommendations.",
        "",
        "## Limitations",
        "",
        "- Matching is deterministic and metadata-only.",
        "- Filename parsing can miss or misread names, months, dates, and UUIDs.",
        "- Month-only audit records do not include a year unless the filename does.",
        "- Candidate links are not evidence of actual QA-to-call correctness.",
        "- No raw content is inspected, extracted, summarized, or transcribed.",
        "",
        "## Privacy And PII Warning",
        "",
        "Treat all outputs as restricted. Filenames and timestamps can still reveal",
        "employee, customer, and operational details even when raw content is not",
        "included.",
        "",
        "## Recommendation On PDF Text Extraction",
        "",
        pdf_extraction_recommendation(review),
        "",
    ]
    return "\n".join(lines)


def render_quality_report(review: dict[str, object]) -> str:
    data_quality = review["data_quality"]
    agent_coverage = review["agent_coverage"]
    link_candidates = review["link_candidates"]

    lines = [
        "# Evidence Quality Report",
        "",
        "This report reviews manifest metadata only and contains no raw PDF, audio,",
        "video, transcript, QA comment, or customer statement content.",
        "",
        "## Data Quality Summary",
        "",
        f"- Missing agent_name: {data_quality['missing_agent_name']}",
        f"- Missing evidence_type: {data_quality['missing_evidence_type']}",
        f"- Missing week_number for audit PDFs: "
        f"{data_quality['missing_week_number_for_audit_pdfs']}",
        f"- Missing recording_date for MP4 recordings: "
        f"{data_quality['missing_recording_date_for_mp4_recordings']}",
        f"- Duplicate file_name rows: {data_quality['duplicate_file_name']}",
        f"- Unknown filename pattern rows: {data_quality['unknown_filename_pattern']}",
        f"- Files without parsed metadata: "
        f"{data_quality['files_without_parsed_metadata']}",
        "",
        "## Duplicate File Names",
        "",
        render_duplicate_table(data_quality["duplicate_file_names"]),
        "",
        "## Agent Coverage Gaps",
        "",
        "### Audit PDFs But No Recordings",
        "",
        render_name_list(agent_coverage["agents_with_audit_pdfs_but_no_recordings"]),
        "",
        "### Recordings But No Audit PDFs",
        "",
        render_name_list(agent_coverage["agents_with_recordings_but_no_audit_pdfs"]),
        "",
        "## Link Candidate Summary",
        "",
        f"- Candidate links generated: {len(link_candidates)}",
        "",
        render_candidate_confidence_table(link_candidates),
        "",
        "## Matching Rules",
        "",
        "- Normalize agent names by lowercasing and removing numeric or hex-like",
        "  fragments often introduced by recording UUIDs.",
        "- High confidence requires same normalized agent, same month, and matching",
        "  audit week range or explicit week number.",
        "- Medium confidence requires same normalized agent with same month, or a",
        "  recording date that falls in an audit week range.",
        "- Low confidence is same normalized agent with incomplete or non-aligned",
        "  period metadata.",
        "",
        "## Privacy And PII Warning",
        "",
        "Review outputs are local-only and restricted. Do not commit generated",
        "review files or use them as runtime product data.",
        "",
    ]
    return "\n".join(lines)


def dataset_value_assessment(
    total: int,
    distinct_agents: int,
    candidate_count: int,
) -> str:
    if total == 0:
        return (
            "No evidence rows are available in the manifest yet. The dataset is not "
            "ready for lineage assessment until local metadata is generated."
        )
    if distinct_agents == 0:
        return (
            "The manifest contains evidence rows, but agent coverage is not parsed. "
            "Improve filename metadata before considering deeper processing."
        )
    if candidate_count == 0:
        return (
            "The manifest has inventory value, but no audit-to-recording candidates "
            "were identified with the current deterministic rules."
        )
    return (
        "The manifest has discovery value for evidence availability, period "
        "coverage, and human-reviewed audit-to-recording lineage candidates."
    )


def pdf_extraction_recommendation(review: dict[str, object]) -> str:
    total = review["inventory"]["total_evidence_files"]
    quality = review["data_quality"]
    if total == 0:
        return (
            "Do not proceed to PDF text extraction yet. First populate and review "
            "the metadata manifest."
        )
    if quality["missing_agent_name"] or quality["missing_evidence_type"]:
        return (
            "Defer PDF text extraction. Resolve missing core metadata and confirm "
            "governance controls before any content-derived processing."
        )
    return (
        "PDF text extraction may be considered later only after privacy controls, "
        "retention rules, redaction, source ownership, and human review gates are "
        "approved. It should remain out of runtime product dependencies."
    )


def count_values(rows: list[dict[str, str]], field: str) -> Counter:
    counter = Counter()
    for row in rows:
        value = value_or_unknown(row.get(field))
        counter[value] += 1
    return counter


def render_counter_table(counter: Counter, label: str, limit: int | None = None) -> str:
    if not counter:
        return "No rows."

    rows = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if limit:
        rows = rows[:limit]

    lines = [
        f"| {label} | Count |",
        "| --- | ---: |",
    ]
    for value, count in rows:
        lines.append(f"| {value} | {count} |")
    return "\n".join(lines)


def render_agent_table(agent_rows: list[dict[str, object]]) -> str:
    if not agent_rows:
        return "No agent rows."

    lines = [
        "| Agent | Evidence | Audits | Recordings |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in agent_rows:
        lines.append(
            f"| {row['agent_name']} | {row['evidence_count']} | "
            f"{row['audit_count']} | {row['recording_count']} |"
        )
    return "\n".join(lines)


def render_duplicate_table(duplicates: dict[str, int]) -> str:
    if not duplicates:
        return "No duplicate file names detected."

    lines = [
        "| File name | Rows |",
        "| --- | ---: |",
    ]
    for file_name, count in duplicates.items():
        lines.append(f"| {file_name} | {count} |")
    return "\n".join(lines)


def render_name_list(names: list[str]) -> str:
    if not names:
        return "None detected."
    return "\n".join(f"- {name}" for name in names)


def render_candidate_confidence_table(candidates: list[dict[str, str]]) -> str:
    confidence_counts = Counter(
        candidate["match_confidence"]
        for candidate in candidates
    )
    return render_counter_table(confidence_counts, "Match confidence")


def is_audit(row: dict[str, str]) -> bool:
    return (
        value_or_unknown(row.get("evidence_type")).lower() == "qa_audit"
        or value_or_unknown(row.get("file_type")).lower() == "pdf"
    )


def is_recording(row: dict[str, str]) -> bool:
    return (
        value_or_unknown(row.get("evidence_type")).lower() == "recording"
        or value_or_unknown(row.get("file_type")).lower() == "mp4"
    )


def is_missing(value: str | None) -> bool:
    return (value or "").strip().lower() in UNKNOWN_VALUES


def value_or_unknown(value: str | None) -> str:
    return "unknown" if is_missing(value) else (value or "").strip()


def normalize_agent_name(agent_name: str | None) -> str:
    if is_missing(agent_name):
        return ""

    cleaned = re.sub(r"[^A-Za-z0-9' ]+", " ", agent_name or "")
    tokens = []
    for token in cleaned.split():
        lowered = token.lower()
        if NUMBER_PATTERN.match(lowered):
            continue
        if HEX_FRAGMENT_PATTERN.match(lowered) and any(char.isdigit() for char in lowered):
            continue
        tokens.append(lowered)
    return " ".join(tokens)


def clean_display_agent_name(agent_name: str | None) -> str:
    normalized = normalize_agent_name(agent_name)
    if not normalized:
        return "unknown"
    return " ".join(part.capitalize() for part in normalized.split())


def months_match(left: str | None, right: str | None) -> bool:
    left_month = month_key(left)
    right_month = month_key(right)
    return left_month is not None and left_month == right_month


def month_key(value: str | None) -> int | tuple[int, int] | None:
    if is_missing(value):
        return None

    normalized = (value or "").strip().lower()
    year_month = re.match(r"^(20\d{2})[-_/ ](0[1-9]|1[0-2])$", normalized)
    if year_month:
        return int(year_month.group(2))

    if normalized in MONTH_NAME_TO_NUMBER:
        return MONTH_NAME_TO_NUMBER[normalized]
    if normalized in MONTH_ABBR_TO_NUMBER:
        return MONTH_ABBR_TO_NUMBER[normalized]
    return None


def weeks_match(left: str | None, right: str | None) -> bool:
    if is_missing(left) or is_missing(right):
        return False
    return str(left).strip() == str(right).strip()


def recording_date_in_audit_week(
    audit: dict[str, str],
    recording: dict[str, str],
) -> bool:
    audit_week = parse_int(audit.get("week_number"))
    recording_date = parse_date(recording.get("recording_date"))
    if audit_week is None or recording_date is None:
        return False

    audit_month_number = month_key(audit.get("month"))
    if audit_month_number is None:
        return False
    if isinstance(audit_month_number, tuple):
        audit_month_number = audit_month_number[1]
    if audit_month_number != recording_date.month:
        return False

    start_day = ((audit_week - 1) * 7) + 1
    end_day = min(audit_week * 7, last_day_of_month(recording_date))
    return start_day <= recording_date.day <= end_day


def parse_int(value: str | None) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    if is_missing(value):
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def last_day_of_month(day: date) -> int:
    return calendar.monthrange(day.year, day.month)[1]


def is_unknown_filename_pattern(row: dict[str, str]) -> bool:
    return is_missing(row.get("agent_name")) or is_missing(row.get("evidence_type"))


def has_no_parsed_metadata(row: dict[str, str]) -> bool:
    parsed_fields = [
        "agent_name",
        "month",
        "week_number",
        "recording_date",
        "recording_time_utc",
        "source_system",
    ]
    return all(is_missing(row.get(field)) for field in parsed_fields)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review a metadata-only QA evidence manifest."
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to qa_evidence_manifest.csv.",
    )
    parser.add_argument(
        "--review-root",
        type=Path,
        default=DEFAULT_REVIEW_ROOT,
        help="Local-only output folder for review artifacts.",
    )
    args = parser.parse_args()

    review, output_paths = review_evidence_manifest(
        manifest_path=args.manifest_path,
        review_root=args.review_root,
    )

    inventory = review["inventory"]
    agent_coverage = review["agent_coverage"]
    print(f"Wrote summary: {output_paths['summary']}")
    print(f"Wrote quality report: {output_paths['quality_report']}")
    print(f"Wrote link candidates: {output_paths['link_candidates']}")
    print(f"Total evidence files: {inventory['total_evidence_files']}")
    print(f"Distinct agents: {agent_coverage['distinct_agents']}")
    print(f"Link candidates: {len(review['link_candidates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
