from typing import Protocol

from app.core.tenant_context import TenantContext
from app.domain.performance.entities import CoachingCommitment
from app.domain.performance.value_objects import CommitmentStatus
from app.infrastructure.persistence.performance._sqlite import (
    date_text,
    datetime_text,
    require_persistence_lineage,
    require_same_tenant,
    scoped_context,
    text_date,
    text_datetime,
)


class CoachingCommitmentRepository(Protocol):
    def save(
        self,
        context: TenantContext | None,
        commitment: CoachingCommitment,
    ) -> None: ...

    def get_by_id(
        self,
        context: TenantContext | None,
        commitment_id: str,
    ) -> CoachingCommitment | None: ...

    def get_commitments(
        self,
        context: TenantContext | None,
        session_id: str,
    ) -> list[CoachingCommitment]: ...


class SQLiteCoachingCommitmentRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, commitment) -> None:
        context = scoped_context(context)
        require_same_tenant(context, commitment.tenant_id)
        require_persistence_lineage(commitment.lineage_id)
        existing = self.get_by_id(context, commitment.commitment_id)
        if existing is not None:
            self._update(context, existing, commitment)
            return

        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO coaching_commitments (
                    tenant_id, commitment_id, session_id, employee_id,
                    description, target_date, lineage_id, status, created_by,
                    updated_by, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                commitment.tenant_id,
                commitment.commitment_id,
                commitment.session_id,
                commitment.employee_id,
                commitment.description,
                date_text(commitment.target_date),
                commitment.lineage_id,
                commitment.status.value,
                commitment.created_by,
                commitment.updated_by,
                datetime_text(commitment.created_at),
                datetime_text(commitment.updated_at),
            ))

    def get_by_id(self, context, commitment_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND commitment_id = ?
            """,
                (context.tenant_id, commitment_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def get_commitments(self, context, session_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND session_id = ?
                ORDER BY created_at, commitment_id
            """,
                (context.tenant_id, session_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _update(self, context, existing, commitment) -> None:
        immutable_fields = (
            "tenant_id",
            "commitment_id",
            "session_id",
            "employee_id",
            "description",
            "target_date",
            "lineage_id",
            "created_by",
            "created_at",
        )
        if any(
            getattr(existing, name) != getattr(commitment, name)
            for name in immutable_fields
        ):
            raise PermissionError("Historical commitment fields are immutable.")
        with self.database_service.connect() as conn:
            conn.execute("""
                UPDATE coaching_commitments
                SET status = ?, updated_by = ?, updated_at = ?
                WHERE tenant_id = ? AND commitment_id = ?
            """, (
                commitment.status.value,
                commitment.updated_by,
                datetime_text(commitment.updated_at),
                context.tenant_id,
                commitment.commitment_id,
            ))

    def _select_sql(self):
        return """
            SELECT tenant_id, commitment_id, session_id, employee_id,
                   description, target_date, lineage_id, created_by,
                   updated_by, status, created_at, updated_at
            FROM coaching_commitments
        """

    def _from_row(self, row):
        return CoachingCommitment(
            tenant_id=row[0],
            commitment_id=row[1],
            session_id=row[2],
            employee_id=row[3],
            description=row[4],
            target_date=text_date(row[5]),
            lineage_id=row[6],
            created_by=row[7],
            updated_by=row[8],
            status=CommitmentStatus.from_value(row[9]),
            created_at=text_datetime(row[10]),
            updated_at=text_datetime(row[11]),
        )
