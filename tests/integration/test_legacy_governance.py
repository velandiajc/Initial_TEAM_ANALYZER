import sqlite3

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.survey import Survey
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.sqlite_agent_repository import SQLiteAgentRepository
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_survey_repository import SQLiteSurveyRepository


def context(tenant_id="tenant-1", roles=None):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="legacy-user",
        roles=roles
        if roles is not None
        else {GovernanceRole.GOVERNANCE_ADMIN.value},
    )


def create_stack(tmp_path):
    database = DatabaseService(tmp_path / "legacy.db")
    database.initialize()
    audit_repository = SQLiteKPIAuditRepository(database)
    audit_service = KPIAuditService(audit_repository)
    return (
        database,
        audit_repository,
        SQLiteAgentRepository(database, audit_service),
        SQLiteSurveyRepository(database, audit_service),
    )


def agent(name):
    return {
        "agent_id": "agent-1",
        "employee_id": "1001",
        "name": name,
        "email": "",
        "nice_name": name,
        "cxone_name": name,
        "status": "Active",
        "supervisor": "",
        "aliases": ["shared-alias"],
    }


def survey(comment="Safe comment"):
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


def test_legacy_repositories_isolate_same_ids_by_tenant(tmp_path):
    _, _, agents, surveys = create_stack(tmp_path)
    agents.upsert_agent(context("tenant-1"), agent("Tenant One Agent"))
    agents.upsert_agent(context("tenant-2"), agent("Tenant Two Agent"))
    surveys.upsert_survey(context("tenant-1"), survey("Tenant one"))
    surveys.upsert_survey(context("tenant-2"), survey("Tenant two"))

    assert agents.find_agent_id(context("tenant-1"), "shared-alias") == "agent-1"
    assert agents.find_agent_id(context("tenant-2"), "shared-alias") == "agent-1"
    assert surveys.all_surveys(context("tenant-1"))[0][5] == "Tenant one"
    assert surveys.all_surveys(context("tenant-2"))[0][5] == "Tenant two"


def test_unauthorized_legacy_access_is_rejected_and_audited(tmp_path):
    _, audit_repository, agents, _ = create_stack(tmp_path)
    unauthorized = context(roles=set())

    with pytest.raises(PermissionError, match="manage_agent_records"):
        agents.upsert_agent(unauthorized, agent("Denied"))

    events = audit_repository.list_events(unauthorized)
    assert events[-1].action == "LEGACY_DATA_ACCESS_DENIED"


def test_legacy_writes_and_reads_generate_audit_events(tmp_path):
    _, audit_repository, agents, surveys = create_stack(tmp_path)
    tenant_context = context()
    agents.upsert_agent(tenant_context, agent("Agent One"))
    agents.find_agent_id(tenant_context, "agent-1")
    surveys.upsert_survey(tenant_context, survey())
    surveys.all_surveys(tenant_context)

    actions = {
        event.action
        for event in audit_repository.list_events(tenant_context)
    }
    assert {
        "AGENT_RECORD_UPSERTED",
        "AGENT_RECORD_LOOKUP",
        "SURVEY_RECORD_UPSERTED",
        "SURVEY_RECORDS_VIEWED",
    } <= actions


def test_pre_tenant_database_is_migrated_without_data_loss(tmp_path):
    path = tmp_path / "pre-tenant.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                employee_id TEXT,
                name TEXT,
                email TEXT,
                nice_name TEXT,
                cxone_name TEXT,
                status TEXT,
                supervisor TEXT
            );
            CREATE TABLE agent_aliases (
                alias TEXT PRIMARY KEY,
                agent_id TEXT
            );
            CREATE TABLE surveys (
                contact_id TEXT PRIMARY KEY,
                agent_id TEXT,
                agent_name TEXT,
                score REAL,
                csat REAL,
                comment TEXT,
                survey_date TEXT,
                brand TEXT,
                media_type TEXT,
                top_reason TEXT,
                disposition TEXT
            );
            INSERT INTO agents VALUES (
                'agent-1', '1001', 'Agent One', '', 'Agent One',
                'Agent One', 'Active', ''
            );
            INSERT INTO agent_aliases VALUES ('agent one', 'agent-1');
            INSERT INTO surveys VALUES (
                'contact-1', 'agent-1', 'Agent One', 9, 90, 'Safe',
                '2026-06-12', 'Test', 'Phone', 'Service', 'Resolved'
            );
        """)

    database = DatabaseService(path, legacy_tenant_id="migrated-tenant")
    database.initialize()
    audit_service = KPIAuditService(SQLiteKPIAuditRepository(database))
    agents = SQLiteAgentRepository(database, audit_service)
    surveys = SQLiteSurveyRepository(database, audit_service)
    migrated_context = context("migrated-tenant")

    assert agents.find_agent_id(migrated_context, "agent one") == "agent-1"
    assert surveys.all_surveys(migrated_context)[0][0] == "contact-1"
    assert surveys.all_surveys(context("other-tenant")) == []
