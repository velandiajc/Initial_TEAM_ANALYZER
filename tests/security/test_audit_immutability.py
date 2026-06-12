import sqlite3

import pytest

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository


def context():
    return TenantContext(
        tenant_id="tenant-1",
        user_id="audit-user",
        roles={GovernanceRole.GOVERNANCE_ADMIN.value},
    )


def create_event(tmp_path):
    database = DatabaseService(tmp_path / "audit.db")
    database.initialize()
    repository = SQLiteKPIAuditRepository(database)
    service = KPIAuditService(repository)
    event = service.record(
        context(),
        action="AUDIT_IMMUTABILITY_TEST",
        entity_type="security_test",
        entity_id="event-1",
    )
    return database, repository, event


def test_audit_insert_remains_valid(tmp_path):
    _, repository, event = create_event(tmp_path)

    assert repository.list_events(context())[-1].event_id == event.event_id


def test_audit_update_is_prohibited_by_sqlite_trigger(tmp_path):
    database, _, event = create_event(tmp_path)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with database.connect() as connection:
            connection.execute(
                """
                UPDATE kpi_audit_events
                SET action = 'TAMPERED'
                WHERE tenant_id = ? AND event_id = ?
                """,
                (context().tenant_id, event.event_id),
            )


def test_audit_delete_is_prohibited_by_sqlite_trigger(tmp_path):
    database, _, event = create_event(tmp_path)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with database.connect() as connection:
            connection.execute(
                """
                DELETE FROM kpi_audit_events
                WHERE tenant_id = ? AND event_id = ?
                """,
                (context().tenant_id, event.event_id),
            )
