from typing import Protocol

from app.core.tenant_context import TenantContext
from app.domain.performance.entities import CoachingFollowUp
from app.domain.performance.value_objects import FollowUpStatus
from app.infrastructure.persistence.performance._sqlite import (
    datetime_text,
    require_persistence_lineage,
    require_same_tenant,
    scoped_context,
    text_datetime,
)


class CoachingFollowUpRepository(Protocol):
    def save(
        self,
        context: TenantContext | None,
        followup: CoachingFollowUp,
    ) -> None: ...

    def get_by_id(
        self,
        context: TenantContext | None,
        followup_id: str,
    ) -> CoachingFollowUp | None: ...

    def get_followups(
        self,
        context: TenantContext | None,
        session_id: str,
    ) -> list[CoachingFollowUp]: ...


class SQLiteCoachingFollowUpRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, followup) -> None:
        context = scoped_context(context)
        require_same_tenant(context, followup.tenant_id)
        require_persistence_lineage(followup.lineage_id)
        existing = self.get_by_id(context, followup.followup_id)
        if existing is not None:
            self._update(context, existing, followup)
            return

        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO coaching_followups (
                    tenant_id, followup_id, session_id, commitment_id,
                    reviewer_id, status, outcome, lineage_id, created_by,
                    updated_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                followup.tenant_id,
                followup.followup_id,
                followup.session_id,
                followup.commitment_id,
                followup.reviewer_id,
                followup.status.value,
                followup.outcome,
                followup.lineage_id,
                followup.created_by,
                followup.updated_by,
                datetime_text(followup.created_at),
                datetime_text(followup.updated_at),
            ))

    def get_by_id(self, context, followup_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND followup_id = ?
            """,
                (context.tenant_id, followup_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def get_followups(self, context, session_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND session_id = ?
                ORDER BY created_at, followup_id
            """,
                (context.tenant_id, session_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _update(self, context, existing, followup) -> None:
        immutable_fields = (
            "tenant_id",
            "followup_id",
            "session_id",
            "commitment_id",
            "reviewer_id",
            "lineage_id",
            "created_by",
            "created_at",
        )
        if any(
            getattr(existing, name) != getattr(followup, name)
            for name in immutable_fields
        ):
            raise PermissionError("Historical follow-up fields are immutable.")
        with self.database_service.connect() as conn:
            conn.execute("""
                UPDATE coaching_followups
                SET status = ?, outcome = ?, updated_by = ?, updated_at = ?
                WHERE tenant_id = ? AND followup_id = ?
            """, (
                followup.status.value,
                followup.outcome,
                followup.updated_by,
                datetime_text(followup.updated_at),
                context.tenant_id,
                followup.followup_id,
            ))

    def _select_sql(self):
        return """
            SELECT tenant_id, followup_id, session_id, commitment_id,
                   reviewer_id, outcome, lineage_id, created_by, updated_by,
                   status, created_at, updated_at
            FROM coaching_followups
        """

    def _from_row(self, row):
        return CoachingFollowUp(
            tenant_id=row[0],
            followup_id=row[1],
            session_id=row[2],
            commitment_id=row[3],
            reviewer_id=row[4],
            outcome=row[5],
            lineage_id=row[6],
            created_by=row[7],
            updated_by=row[8],
            status=FollowUpStatus.from_value(row[9]),
            created_at=text_datetime(row[10]),
            updated_at=text_datetime(row[11]),
        )
