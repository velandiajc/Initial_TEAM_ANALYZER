import csv
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Scripts"
    / "review_evidence_manifest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "review_evidence_manifest",
    SCRIPT_PATH,
)
review_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_manifest)


FIELD_NAMES = [
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


def write_manifest(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(manifest_file, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(rows)


def audit_row(
    file_name="Agent One May Week 1.pdf",
    agent_name="Agent One",
    month="May",
    week_number="1",
):
    return {
        "file_name": file_name,
        "file_type": "pdf",
        "evidence_type": "qa_audit",
        "agent_name": agent_name,
        "month": month,
        "week_number": week_number,
        "recording_date": "unknown",
        "recording_time_utc": "unknown",
        "source_system": "qa_audit",
        "source_uuid": "unknown",
        "file_size_bytes": "100",
        "local_file_reference": f"data/raw/evidence_samples/audits/{file_name}",
        "sensitivity": "restricted",
        "processing_status": "metadata_only",
    }


def recording_row(
    file_name="CXone recording_Agent One_2026-05-06_16-10[UTC]_abc123.mp4",
    agent_name="Agent One abc123",
    month="2026-05",
    recording_date="2026-05-06",
    recording_time_utc="16:10:00",
):
    return {
        "file_name": file_name,
        "file_type": "mp4",
        "evidence_type": "recording",
        "agent_name": agent_name,
        "month": month,
        "week_number": "unknown",
        "recording_date": recording_date,
        "recording_time_utc": recording_time_utc,
        "source_system": "cxone",
        "source_uuid": "unknown",
        "file_size_bytes": "200",
        "local_file_reference": f"data/raw/evidence_samples/recordings/{file_name}",
        "sensitivity": "restricted",
        "processing_status": "metadata_only",
    }


def test_inventory_summary_generation():
    rows = [
        audit_row(),
        recording_row(),
        audit_row(
            file_name="Agent Two May Week 1.pdf",
            agent_name="Agent Two",
        ),
    ]

    review = review_manifest.build_review(rows)
    inventory = review["inventory"]

    assert inventory["total_evidence_files"] == 3
    assert inventory["count_by_evidence_type"]["qa_audit"] == 2
    assert inventory["count_by_evidence_type"]["recording"] == 1
    assert inventory["count_by_file_type"]["pdf"] == 2
    assert inventory["count_by_file_type"]["mp4"] == 1
    assert inventory["count_by_sensitivity"]["restricted"] == 3
    assert inventory["count_by_processing_status"]["metadata_only"] == 3


def test_agent_coverage_calculations():
    rows = [
        audit_row(),
        recording_row(),
        audit_row(
            file_name="Agent Two May Week 1.pdf",
            agent_name="Agent Two",
        ),
    ]

    review = review_manifest.build_review(rows)
    coverage = review["agent_coverage"]

    assert coverage["distinct_agents"] == 2
    assert coverage["audit_count_per_agent"]["Agent One"] == 1
    assert coverage["recording_count_per_agent"]["Agent One"] == 1
    assert coverage["audit_count_per_agent"]["Agent Two"] == 1
    assert coverage["recording_count_per_agent"]["Agent Two"] == 0
    assert coverage["agents_with_audit_pdfs_but_no_recordings"] == ["Agent Two"]


def test_missing_metadata_detection():
    rows = [
        audit_row(
            file_name="Unknown Audit.pdf",
            agent_name="unknown",
            week_number="unknown",
        ),
        recording_row(
            file_name="Unknown Recording.mp4",
            agent_name="unknown",
            recording_date="unknown",
        ),
        {
            **audit_row(file_name="Missing Type.pdf"),
            "evidence_type": "",
        },
    ]

    review = review_manifest.build_review(rows)
    quality = review["data_quality"]

    assert quality["missing_agent_name"] == 2
    assert quality["missing_evidence_type"] == 1
    assert quality["missing_week_number_for_audit_pdfs"] == 1
    assert quality["missing_recording_date_for_mp4_recordings"] == 1
    assert quality["unknown_filename_pattern"] == 3


def test_duplicate_filename_detection():
    rows = [
        audit_row(file_name="Duplicate.pdf"),
        audit_row(file_name="Duplicate.pdf"),
        recording_row(file_name="Unique.mp4"),
    ]

    review = review_manifest.build_review(rows)
    quality = review["data_quality"]

    assert quality["duplicate_file_name"] == 2
    assert quality["duplicate_file_names"] == {"Duplicate.pdf": 2}


def test_audit_to_recording_link_candidate_generation():
    rows = [
        audit_row(
            file_name="Agent One May Week 1.pdf",
            agent_name="Agent One",
            month="May",
            week_number="1",
        ),
        recording_row(
            file_name="CXone recording_Agent One_2026-05-06_16-10[UTC]_abc123.mp4",
            agent_name="Agent One abc123",
            month="2026-05",
            recording_date="2026-05-06",
        ),
        recording_row(
            file_name="CXone recording_Agent Two_2026-05-06_16-10[UTC]_def456.mp4",
            agent_name="Agent Two def456",
            month="2026-05",
            recording_date="2026-05-06",
        ),
    ]

    review = review_manifest.build_review(rows)
    candidates = review["link_candidates"]

    assert len(candidates) == 1
    assert candidates[0]["agent_name"] == "Agent One"
    assert candidates[0]["audit_file_name"] == "Agent One May Week 1.pdf"
    assert candidates[0]["recording_file_name"].startswith("CXone recording_Agent One")
    assert candidates[0]["match_confidence"] == "high"
    assert "same normalized agent" in candidates[0]["match_reason"]


def test_generated_outputs_do_not_include_raw_pdf_or_mp4_content(tmp_path):
    raw_content = "raw customer call statement should not be copied"
    manifest_path = tmp_path / "manifest" / "qa_evidence_manifest.csv"
    review_root = tmp_path / "review"
    rows = [
        audit_row(file_name="Agent One May Week 1.pdf"),
        recording_row(file_name="CXone recording_Agent One_2026-05-06.mp4"),
    ]
    write_manifest(manifest_path, rows)

    review, output_paths = review_manifest.review_evidence_manifest(
        manifest_path=manifest_path,
        review_root=review_root,
    )

    assert review["inventory"]["total_evidence_files"] == 2
    for output_path in output_paths.values():
        content = output_path.read_text(encoding="utf-8")
        assert raw_content not in content
        assert "metadata only" in content.lower() or output_path.suffix == ".csv"


def test_script_handles_empty_manifest_gracefully(tmp_path):
    manifest_path = tmp_path / "manifest" / "qa_evidence_manifest.csv"
    review_root = tmp_path / "review"
    write_manifest(manifest_path, [])

    review, output_paths = review_manifest.review_evidence_manifest(
        manifest_path=manifest_path,
        review_root=review_root,
    )

    assert review["inventory"]["total_evidence_files"] == 0
    assert review["agent_coverage"]["distinct_agents"] == 0
    assert review["link_candidates"] == []
    assert output_paths["summary"].exists()
    assert output_paths["quality_report"].exists()
    assert output_paths["link_candidates"].exists()
    summary = output_paths["summary"].read_text(encoding="utf-8")
    assert "No evidence rows are available" in summary
