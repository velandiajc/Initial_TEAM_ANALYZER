from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import re
from pathlib import Path

from app.services.pci_redaction_service import PCIRedactionService


DEFAULT_RAW_ROOT = Path("data/raw/evidence_samples")
DEFAULT_OUTPUT_ROOT = Path("data/processed/evidence")

MANIFEST_FIELDS = [
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

SUPPORTED_SUFFIXES = {".pdf", ".mp4"}
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
DATE_PATTERNS = [
    re.compile(r"(?<!\d)(20\d{2})[-_. ](0[1-9]|1[0-2])[-_. ]([0-3]\d)(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-3]\d)(?!\d)"),
]
TIME_PATTERN = re.compile(
    r"(?<!\d)([01]\d|2[0-3])[-_:]?([0-5]\d)(?:[-_:]?([0-5]\d))?"
    r"(?:\s?(?:UTC|Z))?(?!\d)",
    re.IGNORECASE,
)
WEEK_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:week|wk)[-_ ]*([0-9]{1,2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)

MONTH_LOOKUP = {}
for index, month_name in enumerate(calendar.month_name):
    if month_name:
        MONTH_LOOKUP[month_name.lower()] = (index, month_name)
for index, month_name in enumerate(calendar.month_abbr):
    if month_name:
        MONTH_LOOKUP[month_name.lower()] = (index, calendar.month_name[index])

MONTH_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z])("
    + "|".join(sorted((re.escape(key) for key in MONTH_LOOKUP), key=len, reverse=True))
    + r")(?![A-Za-z])",
    re.IGNORECASE,
)

AGENT_STOPWORDS = {
    "audit",
    "audits",
    "call",
    "calls",
    "contact",
    "cxone",
    "evaluation",
    "evaluations",
    "id",
    "interaction",
    "interactions",
    "media",
    "mp4",
    "pdf",
    "player",
    "qa",
    "quality",
    "recording",
    "recordings",
    "scorecard",
    "source",
    "system",
    "t",
    "transcript",
    "utc",
    "uuid",
    "wk",
    "week",
    "z",
}


def scan_evidence_files(raw_root: Path = DEFAULT_RAW_ROOT) -> list[Path]:
    """Return supported local evidence files without opening raw content."""
    if not raw_root.exists():
        return []

    return sorted(
        path
        for path in raw_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def parse_evidence_file(path: Path, raw_root: Path = DEFAULT_RAW_ROOT) -> dict[str, str]:
    file_type = path.suffix.lower().lstrip(".")
    evidence_type = "qa_audit" if file_type == "pdf" else "recording"
    stem = path.stem
    recording_date = extract_recording_date(stem)

    row = {
        "file_name": path.name,
        "file_type": file_type,
        "evidence_type": evidence_type,
        "agent_name": infer_agent_name(stem),
        "month": extract_month(stem, recording_date),
        "week_number": extract_week_number(stem),
        "recording_date": recording_date,
        "recording_time_utc": extract_recording_time_utc(stem),
        "source_system": infer_source_system(stem, file_type),
        "source_uuid": extract_source_uuid(stem),
        "file_size_bytes": str(path.stat().st_size),
        "local_file_reference": local_file_reference(path, raw_root),
        "sensitivity": "restricted",
        "processing_status": "metadata_only",
    }
    return row


def build_manifest_rows(raw_root: Path = DEFAULT_RAW_ROOT) -> list[dict[str, str]]:
    return [
        parse_evidence_file(path, raw_root)
        for path in scan_evidence_files(raw_root)
    ]


def write_manifest(
    rows: list[dict[str, str]],
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> Path:
    manifest_path = output_root / "manifest" / "qa_evidence_manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(
            PCIRedactionService().redact_structure(rows)
        )

    return manifest_path


def write_markdown_metadata(
    rows: list[dict[str, str]],
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> list[Path]:
    audit_dir = output_root / "markdown" / "audits"
    recording_dir = output_root / "markdown" / "recordings"
    audit_dir.mkdir(parents=True, exist_ok=True)
    recording_dir.mkdir(parents=True, exist_ok=True)

    for markdown_dir in (audit_dir, recording_dir):
        for existing_file in markdown_dir.glob("*.md"):
            existing_file.unlink()

    written_files = []
    for row in rows:
        target_dir = audit_dir if row["evidence_type"] == "qa_audit" else recording_dir
        target_path = target_dir / markdown_file_name(row)
        target_path.write_text(render_markdown_metadata(row), encoding="utf-8")
        written_files.append(target_path)

    return written_files


def build_evidence_manifest(
    raw_root: Path = DEFAULT_RAW_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[Path, list[Path], list[dict[str, str]]]:
    rows = build_manifest_rows(raw_root)
    manifest_path = write_manifest(rows, output_root)
    markdown_paths = write_markdown_metadata(rows, output_root)
    return manifest_path, markdown_paths, rows


def extract_source_uuid(stem: str) -> str:
    match = UUID_PATTERN.search(stem)
    return match.group(0) if match else "unknown"


def extract_recording_date(stem: str) -> str:
    for pattern in DATE_PATTERNS:
        match = pattern.search(stem)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"
    return "unknown"


def extract_recording_time_utc(stem: str) -> str:
    without_dates = remove_known_dates(stem)
    without_dates = re.sub(r"\b20\d{2}\b", " ", without_dates)
    match = TIME_PATTERN.search(without_dates)
    if not match:
        return "unknown"

    hour, minute, second = match.groups()
    return f"{hour}:{minute}:{second or '00'}"


def extract_week_number(stem: str) -> str:
    match = WEEK_PATTERN.search(stem)
    return match.group(1) if match else "unknown"


def extract_month(stem: str, recording_date: str = "unknown") -> str:
    year_month = re.search(r"(?<!\d)(20\d{2})[-_ ](0[1-9]|1[0-2])(?!\d)", stem)
    if year_month:
        return f"{year_month.group(1)}-{year_month.group(2)}"

    month_year = re.search(
        MONTH_TOKEN_PATTERN.pattern + r"[-_ ]+(20\d{2})",
        stem,
        re.IGNORECASE,
    )
    if month_year:
        month_number, _ = MONTH_LOOKUP[month_year.group(1).lower()]
        return f"{month_year.group(2)}-{month_number:02d}"

    year_then_month = re.search(
        r"(20\d{2})[-_ ]+" + MONTH_TOKEN_PATTERN.pattern,
        stem,
        re.IGNORECASE,
    )
    if year_then_month:
        month_number, _ = MONTH_LOOKUP[year_then_month.group(2).lower()]
        return f"{year_then_month.group(1)}-{month_number:02d}"

    month_match = MONTH_TOKEN_PATTERN.search(stem)
    if month_match:
        _, month_name = MONTH_LOOKUP[month_match.group(1).lower()]
        return month_name

    if recording_date != "unknown":
        return recording_date[:7]

    return "unknown"


def infer_source_system(stem: str, file_type: str) -> str:
    if "cxone" in stem.lower() or file_type == "mp4":
        return "cxone"
    if file_type == "pdf":
        return "qa_audit"
    return "unknown"


def infer_agent_name(stem: str) -> str:
    cleaned = UUID_PATTERN.sub(" ", stem)
    cleaned = remove_known_dates(cleaned)
    cleaned = TIME_PATTERN.sub(" ", cleaned)
    cleaned = WEEK_PATTERN.sub(" ", cleaned)
    cleaned = MONTH_TOKEN_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\b20\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"[_\-\.]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    tokens = []
    for token in cleaned.split(" "):
        normalized = re.sub(r"[^A-Za-z0-9']", "", token)
        if not normalized:
            continue
        if normalized.lower() in AGENT_STOPWORDS:
            continue
        if normalized.isdigit():
            continue
        tokens.append(normalized)

    return " ".join(tokens) if tokens else "unknown"


def remove_known_dates(value: str) -> str:
    cleaned = value
    for pattern in DATE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return cleaned


def local_file_reference(path: Path, raw_root: Path) -> str:
    try:
        relative_path = path.relative_to(raw_root)
        return (Path("data/raw/evidence_samples") / relative_path).as_posix()
    except ValueError:
        return path.as_posix()


def markdown_file_name(row: dict[str, str]) -> str:
    safe_stem = PCIRedactionService().redact_filename_component(
        Path(row["file_name"]).stem
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", safe_stem).strip("-")
    digest = hashlib.sha256(
        row["local_file_reference"].encode("utf-8")
    ).hexdigest()[:8]
    return f"{row['evidence_type']}-{slug.lower()}-{digest}.md"


def render_markdown_metadata(row: dict[str, str]) -> str:
    lines = [
        "# Evidence Metadata",
        "",
        "This file contains metadata only. It does not include PDF text, audio,",
        "video, transcript content, QA comments, customer statements, or call content.",
        "",
    ]
    for field in MANIFEST_FIELDS:
        lines.append(f"- **{field}:** {row[field]}")
    lines.append("")
    return PCIRedactionService().redact("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a metadata-only QA evidence manifest."
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
        help="Evidence sample root to scan.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Processed evidence output root.",
    )
    args = parser.parse_args()

    manifest_path, markdown_paths, rows = build_evidence_manifest(
        raw_root=args.raw_root,
        output_root=args.output_root,
    )
    print(f"Wrote manifest: {manifest_path}")
    print(f"Wrote markdown files: {len(markdown_paths)}")
    print(f"Evidence files scanned: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
