import sqlite3
from typing import Protocol

from app.core.tenant_context import TenantContext
from app.domain.performance.entities import EmployeePerformanceTimelineEvent
from app.domain.performance.value_objects import PerformanceTimelineEventSource
from app.infrastructure.persistence.performance._sqlite import (
    datetime_text,
    require_persistence_lineage,
    require_same_tenant,
    scoped_context,
    text_datetime,
)


class EmployeePerformanceTimelineRepository(Protocol):
    def save(
        self,
        context: TenantContext | None,
        event: EmployeePerformanceTimelineEvent,
    ) -> None: ...

    def get_timeline(
        self,
        context: TenantContext | None,
        employee_id: str,
    ) -> list[EmployeePerformanceTimelineEvent]: ...


class SQLiteEmployeePerformanceTimelineRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, event) -> None:
        context = scoped_context(context)
        require_same_tenant(context, event.tenant_id)
        require_persistence_lineage(event.lineage_id)
        try:
            with self.database_service.connect() as conn:
                conn.execute("""
                    INSERT INTO performance_timeline_events (
                        tenant_id, timeline_event_id, employee_id, event_type,
                        event_source, source_entity_id, lineage_id, created_by,
                        updated_by, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.tenant_id,
                    event.timeline_event_id,
                    event.employee_id,
                    event.event_type,
                    event.event_source.value,
                    event.source_entity_id,
                    event.lineage_id,
                    event.created_by,
                    event.updated_by,
                    datetime_text(event.created_at),
                    datetime_text(event.updated_at),
                ))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Duplicate performance timeline event.") from exc

    def get_timeline(self, context, employee_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute("""
                SELECT tenant_id, timeline_event_id, employee_id, event_type,
                       event_source, source_entity_id, lineage_id, created_by,
                       updated_by, created_at, updated_at
                FROM performance_timeline_events
                WHERE tenant_id = ? AND employee_id = ?
                ORDER BY created_at, timeline_event_id
            """, (context.tenant_id, employee_id)).fetchall()
        return [self._from_row(row) for row in rows]

    def _from_row(self, row):
        return EmployeePerformanceTimelineEvent(
            tenant_id=row[0],
            timeline_event_id=row[1],
            employee_id=row[2],
            event_type=row[3],
            event_source=PerformanceTimelineEventSource.from_value(row[4]),
            source_entity_id=row[5],
            lineage_id=row[6],
            created_by=row[7],
            updated_by=row[8],
            created_at=text_datetime(row[9]),
            updated_at=text_datetime(row[10]),
        )
