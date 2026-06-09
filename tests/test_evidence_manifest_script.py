import csv
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Scripts"
    / "build_evidence_manifest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_evidence_manifest",
    SCRIPT_PATH,
)
evidence_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence_manifest)


def write_sample(path, content="placeholder sample content"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_pdf_audit_filename_parsing(tmp_path):
    raw_root = tmp_path / "data" / "raw" / "evidence_samples"
    audit_path = raw_root / "audits" / "QA Audit - Agent One - March - Week 2.pdf"
    write_sample(audit_path)

    row = evidence_manifest.parse_evidence_file(audit_path, raw_root)

    assert row["file_name"] == audit_path.name
    assert row["file_type"] == "pdf"
    assert row["evidence_type"] == "qa_audit"
    assert row["agent_name"] == "Agent One"
    assert row["month"] == "March"
    assert row["week_number"] == "2"
    assert row["recording_date"] == "unknown"
    assert row["recording_time_utc"] == "unknown"
    assert row["source_system"] == "qa_audit"


def test_cxone_recording_filename_parsing(tmp_path):
    raw_root = tmp_path / "data" / "raw" / "evidence_samples"
    source_uuid = "123e4567-e89b-12d3-a456-426614174000"
    recording_path = (
        raw_root
        / "recordings"
        / f"CXone Recording - Agent Two - 2026-05-17T18-30-45Z - {source_uuid}.mp4"
    )
    write_sample(recording_path)

    row = evidence_manifest.parse_evidence_file(recording_path, raw_root)

    assert row["file_type"] == "mp4"
    assert row["evidence_type"] == "recording"
    assert row["agent_name"] == "Agent Two"
    assert row["month"] == "2026-05"
    assert row["recording_date"] == "2026-05-17"
    assert row["recording_time_utc"] == "18:30:45"
    assert row["source_system"] == "cxone"
    assert row["source_uuid"] == source_uuid


def test_unknown_filename_handling(tmp_path):
    raw_root = tmp_path / "data" / "raw" / "evidence_samples"
    audit_path = raw_root / "audits" / "QA_Audit_2026_Week_2.pdf"
    write_sample(audit_path)

    row = evidence_manifest.parse_evidence_file(audit_path, raw_root)

    assert row["agent_name"] == "unknown"
    assert row["month"] == "unknown"
    assert row["week_number"] == "2"
    assert row["source_uuid"] == "unknown"


def test_manifest_row_generation(tmp_path):
    raw_root = tmp_path / "data" / "raw" / "evidence_samples"
    audit_path = raw_root / "audits" / "QA Audit - Agent One - March - Week 2.pdf"
    recording_path = (
        raw_root
        / "recordings"
        / "CXone Recording - Agent Two - 2026-05-17T18-30-45Z.mp4"
    )
    ignored_path = raw_root / "recordings" / "notes.txt"
    write_sample(audit_path)
    write_sample(recording_path)
    write_sample(ignored_path)

    rows = evidence_manifest.build_manifest_rows(raw_root)

    assert [row["file_name"] for row in rows] == [
        audit_path.name,
        recording_path.name,
    ]
    assert all(row["sensitivity"] == "restricted" for row in rows)
    assert all(row["processing_status"] == "metadata_only" for row in rows)


def test_markdown_metadata_generation_excludes_raw_content(tmp_path):
    raw_root = tmp_path / "data" / "raw" / "evidence_samples"
    output_root = tmp_path / "data" / "processed" / "evidence"
    raw_content = "customer statement and call details should never appear"
    audit_path = raw_root / "audits" / "QA Audit - Agent One - March - Week 2.pdf"
    write_sample(audit_path, raw_content)

    manifest_path, markdown_paths, rows = evidence_manifest.build_evidence_manifest(
        raw_root=raw_root,
        output_root=output_root,
    )

    assert manifest_path.exists()
    assert len(markdown_paths) == 1
    markdown = markdown_paths[0].read_text(encoding="utf-8")
    assert rows[0]["file_name"] in markdown
    assert "metadata only" in markdown.lower()
    assert raw_content not in markdown


def test_manifest_csv_generation(tmp_path):
    raw_root = tmp_path / "data" / "raw" / "evidence_samples"
    output_root = tmp_path / "data" / "processed" / "evidence"
    audit_path = raw_root / "audits" / "QA Audit - Agent One - March - Week 2.pdf"
    write_sample(audit_path)

    manifest_path, _, _ = evidence_manifest.build_evidence_manifest(
        raw_root=raw_root,
        output_root=output_root,
    )

    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        rows = list(csv.DictReader(manifest_file))

    assert len(rows) == 1
    assert rows[0]["file_name"] == audit_path.name
    assert rows[0]["sensitivity"] == "restricted"
    assert rows[0]["processing_status"] == "metadata_only"
