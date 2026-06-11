from typing import Protocol

from app.core.tenant_context import TenantContext
from app.domain.performance.entities import CoachingNote
from app.domain.performance.value_objects import CoachingNoteVisibility
from app.infrastructure.persistence.performance._sqlite import (
    datetime_text,
    require_persistence_lineage,
    require_same_tenant,
    scoped_context,
    text_datetime,
)


class CoachingNoteRepository(Protocol):
    def save(
        self,
        context: TenantContext | None,
        note: CoachingNote,
    ) -> None: ...

    def get_note(
        self,
        context: TenantContext | None,
        note_id: str,
    ) -> CoachingNote | None: ...

    def list_for_session(
        self,
        context: TenantContext | None,
        session_id: str,
    ) -> list[CoachingNote]: ...


class SQLiteCoachingNoteRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, note) -> None:
        context = scoped_context(context)
        require_same_tenant(context, note.tenant_id)
        require_persistence_lineage(note.lineage_id)
        if self.get_note(context, note.note_id) is not None:
            raise PermissionError("Coaching notes are immutable.")

        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO coaching_notes (
                    tenant_id, note_id, session_id, visibility_level,
                    content_reference, lineage_id, created_by, updated_by,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                note.tenant_id,
                note.note_id,
                note.session_id,
                note.visibility_level.value,
                note.content_reference,
                note.lineage_id,
                note.created_by,
                note.updated_by,
                datetime_text(note.created_at),
                datetime_text(note.updated_at),
            ))

    def get_note(self, context, note_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND note_id = ?
            """,
                (context.tenant_id, note_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_session(self, context, session_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select_sql() + """
                WHERE tenant_id = ? AND session_id = ?
                ORDER BY created_at, note_id
            """,
                (context.tenant_id, session_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _select_sql(self):
        return """
            SELECT tenant_id, note_id, session_id, visibility_level,
                   content_reference, lineage_id, created_by, updated_by,
                   created_at, updated_at
            FROM coaching_notes
        """

    def _from_row(self, row):
        return CoachingNote(
            tenant_id=row[0],
            note_id=row[1],
            session_id=row[2],
            visibility_level=CoachingNoteVisibility.from_value(row[3]),
            content_reference=row[4],
            lineage_id=row[5],
            created_by=row[6],
            updated_by=row[7],
            created_at=text_datetime(row[8]),
            updated_at=text_datetime(row[9]),
        )
