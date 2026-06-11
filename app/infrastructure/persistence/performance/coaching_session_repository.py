import json
from typing import Protocol

from app.core.tenant_context import TenantContext
from app.domain.performance.entities import CoachingSession
from app.domain.performance.rules.coaching_snapshot_rules import (
    reject_snapshot_mutation,
)
from app.domain.performance.value_objects import CoachingSessionStatus
from app.infrastructure.persistence.performance._sqlite import (
    datetime_text,
    require_persistence_lineage,
    require_same_tenant,
    scoped_context,
    text_datetime,
)


class CoachingSessionRepository(Protocol):
    def save(
        self,
        context: TenantContext | None,
        session: CoachingSession,
    ) -> None: ...

    def get_session(
        self,
        context: TenantContext | None,
        session_id: str,
    ) -> CoachingSession | None: ...

    def list_for_employee(
        self,
        context: TenantContext | None,
        employee_id: str,
    ) -> list[CoachingSession]: ...


class SQLiteCoachingSessionRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, session) -> None:
        context = scoped_context(context)
        require_same_tenant(context, session.tenant_id)
        require_persistence_lineage(
            session.lineage_id,
            session.evidence_pack_id,
            session.risk_result_id,
        )
        existing = self.get_session(context, session.coaching_session_id)
        if existing is not None:
            reject_snapshot_mutation(existing, session)
            self._update(context, session)
            return

        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO coaching_sessions (
                    tenant_id, coaching_session_id, employee_id,
                    session_owner_id, performance_opportunity_id,
                    evidence_pack_id, evidence_version_snapshot,
                    evidence_artifact_ids_snapshot_json, risk_result_id,
                    risk_score_snapshot, risk_level_snapshot,
                    risk_classification_snapshot, risk_definition_version,
                    risk_rule_version, coaching_version, lineage_id, status,
                    created_by, updated_by, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                session.tenant_id,
                session.coaching_session_id,
                session.employee_id,
                session.session_owner_id,
                session.performance_opportunity_id,
                session.evidence_pack_id,
                session.evidence_version_snapshot,
                json.dumps(session.evidence_artifact_ids_snapshot),
                session.risk_result_id,
                session.risk_score_snapshot,
                session.risk_level_snapshot,
                session.risk_classification_snapshot,
                session.risk_definition_version,
                session.risk_rule_version,
                session.coaching_version,
                session.lineage_id,
                session.status.value,
                session.created_by,
                session.updated_by,
                datetime_text(session.created_at),
                datetime_text(session.updated_at),
            ))

    def get_session(self, context, session_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND coaching_session_id = ?
            """,
                (context.tenant_id, session_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_employee(self, context, employee_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND employee_id = ?
                ORDER BY created_at, coaching_session_id
            """,
                (context.tenant_id, employee_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _update(self, context, session) -> None:
        with self.database_service.connect() as conn:
            conn.execute("""
                UPDATE coaching_sessions
                SET status = ?, updated_by = ?, updated_at = ?
                WHERE tenant_id = ? AND coaching_session_id = ?
            """, (
                session.status.value,
                session.updated_by,
                datetime_text(session.updated_at),
                context.tenant_id,
                session.coaching_session_id,
            ))

    def _select_sql(self):
        return """
            SELECT tenant_id, coaching_session_id, employee_id,
                   session_owner_id, performance_opportunity_id,
                   evidence_pack_id, evidence_version_snapshot,
                   evidence_artifact_ids_snapshot_json, risk_result_id,
                   risk_score_snapshot, risk_level_snapshot,
                   risk_classification_snapshot, risk_definition_version,
                   risk_rule_version, coaching_version, lineage_id, created_by,
                   updated_by, status, created_at, updated_at
            FROM coaching_sessions
        """

    def _from_row(self, row):
        return CoachingSession(
            tenant_id=row[0],
            coaching_session_id=row[1],
            employee_id=row[2],
            session_owner_id=row[3],
            performance_opportunity_id=row[4],
            evidence_pack_id=row[5],
            evidence_version_snapshot=row[6],
            evidence_artifact_ids_snapshot=tuple(json.loads(row[7] or "[]")),
            risk_result_id=row[8],
            risk_score_snapshot=row[9],
            risk_level_snapshot=row[10],
            risk_classification_snapshot=row[11],
            risk_definition_version=row[12],
            risk_rule_version=row[13],
            coaching_version=row[14],
            lineage_id=row[15],
            created_by=row[16],
            updated_by=row[17],
            status=CoachingSessionStatus.from_value(row[18]),
            created_at=text_datetime(row[19]),
            updated_at=text_datetime(row[20]),
        )
