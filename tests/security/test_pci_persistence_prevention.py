import sqlite3

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.survey import Survey
from app.models.transcript import Transcript
from app.services.agent_registry import AgentRegistry
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.sqlite_agent_repository import SQLiteAgentRepository
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_survey_repository import SQLiteSurveyRepository
from app.services.survey_analytics_service import SurveyAnalyticsService
from app.services.survey_insight_service import SurveyInsightService
from app.services.transcript_repository import TranscriptRepository
from app.services.workbook_ingestion_service import WorkbookIngestionService
from Scripts import call_analyzer
from Scripts.transcribe_calls import write_redacted_transcript


def context():
    return TenantContext(
        tenant_id="tenant-1",
        user_id="security-test",
        roles={GovernanceRole.GOVERNANCE_ADMIN.value},
    )


def survey(comment):
    return Survey(
        contact_id="contact-1",
        agent_id="agent-1",
        agent_name="Agent One",
        score=9,
        comment=comment,
        survey_date="2026-06-12",
        brand="Test",
        media_type="Phone",
        top_reason="Service",
        disposition="Resolved",
    )


def test_transcript_file_and_repository_never_store_pan_or_cvv(tmp_path):
    unsafe = "Card 4111 1111 1111 1111 and CVV 123."
    output_path = write_redacted_transcript(
        tmp_path / "transcript.md",
        unsafe,
    )
    repository = TranscriptRepository()
    repository.add(
        Transcript(
            call_id="call-1",
            raw_text=unsafe,
            customer_sentiment="neutral",
            resolution_type="resolved",
            topics=[],
        )
    )

    assert "4111" not in output_path.read_text(encoding="utf-8")
    assert "123" not in output_path.read_text(encoding="utf-8")
    assert "4111" not in repository.get("call-1").raw_text
    assert "123" not in repository.get("call-1").raw_text


def test_call_analysis_markdown_uses_redacted_transcript(tmp_path, monkeypatch):
    transcript_path = tmp_path / "call.md"
    transcript_path.write_text(
        "Customer gave 4111111111111111 and security code 123.",
        encoding="utf-8",
    )
    output_folder = tmp_path / "analysis"
    output_folder.mkdir()
    monkeypatch.setattr(call_analyzer, "OUTPUT_FOLDER", output_folder)

    output_path = call_analyzer.generate_markdown(transcript_path)
    result = output_path.read_text(encoding="utf-8")

    assert "4111111111111111" not in result
    assert "security code 123" not in result.lower()
    assert "[REDACTED PAN]" in result
    assert "[REDACTED CVV]" in result


def test_survey_database_and_reports_do_not_persist_pan_or_cvv(tmp_path):
    database = DatabaseService(tmp_path / "pci.db")
    database.initialize()
    audit_service = KPIAuditService(SQLiteKPIAuditRepository(database))
    SQLiteAgentRepository(database, audit_service).upsert_agent(
        context(),
        {
            "agent_id": "agent-1",
            "employee_id": "1001",
            "name": "Agent One",
            "aliases": [],
        },
    )
    repository = SQLiteSurveyRepository(database, audit_service)
    unsafe_survey = survey(
        "Use 5555-5555-5555-4444 with card verification code 987."
    )

    repository.upsert_survey(context(), unsafe_survey)
    stored = repository.all_surveys(context())[0][5]

    insight_path = tmp_path / "survey_insights.md"
    SurveyInsightService(
        [unsafe_survey],
        AgentRegistry(),
    ).export_markdown_report(insight_path)
    analytics_path = tmp_path / "survey_summary.csv"
    SurveyAnalyticsService(
        [unsafe_survey],
        AgentRegistry(),
    ).export_agent_summary(analytics_path)

    for persisted in (
        stored,
        insight_path.read_text(encoding="utf-8"),
        analytics_path.read_text(encoding="utf-8-sig"),
    ):
        assert "5555-5555-5555-4444" not in persisted
        assert "987" not in persisted


def test_workbook_inventory_redacts_pan_and_cvv():
    service = WorkbookIngestionService()
    inventory = service.build_inventory_from_sheets(
        "source.xlsx",
        [
            {
                "sheet_name": "Survey",
                "header_row_number": 1,
                "column_names": ["Comment"],
                "rows": [
                    ["4111111111111111 CVV 123"],
                ],
            }
        ],
    )
    markdown = service.render_inventory_markdown(inventory)

    assert "4111111111111111" not in markdown
    assert "CVV 123" not in markdown


def test_audit_metadata_redacts_card_data_even_under_allowed_key(tmp_path):
    database = DatabaseService(tmp_path / "audit-pci.db")
    database.initialize()
    repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(repository)

    audit_service.record(
        context(),
        action="PCI_TEST",
        entity_type="security_test",
        entity_id="event-1",
        metadata={
            "message": "PAN 4111111111111111 and cvc 321",
        },
    )
    event = repository.list_events(context())[-1]

    assert event.metadata["message"] == (
        "PAN [REDACTED PAN] and cvc [REDACTED CVV]"
    )


def test_sqlite_rejects_unsanitized_card_data_in_any_text_column(tmp_path):
    database = DatabaseService(tmp_path / "database-guard.db")
    database.initialize()

    with pytest.raises(sqlite3.IntegrityError, match="PCI data persistence"):
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO agents (
                    tenant_id,
                    agent_id,
                    name
                )
                VALUES (?, ?, ?)
                """,
                ("tenant-1", "agent-1", "4111111111111111"),
            )

    with pytest.raises(sqlite3.IntegrityError, match="PCI data persistence"):
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO kpi_audit_events (
                    tenant_id,
                    event_id,
                    action,
                    actor_user_id,
                    entity_type,
                    entity_id,
                    occurred_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tenant-1",
                    "event-1",
                    "TEST",
                    "user-1",
                    "test",
                    "entity-1",
                    "2026-06-12T00:00:00",
                    '{"cvv": "123"}',
                ),
            )
