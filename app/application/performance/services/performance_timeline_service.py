from uuid import uuid4

from app.application.performance.services._service import (
    PerformanceServiceSupport,
)
from app.core.permissions import CoachingPermission
from app.domain.performance.entities import EmployeePerformanceTimelineEvent
from app.domain.performance.value_objects import (
    CoachingAuditEvent,
    PerformanceTimelineEventSource,
)


class EmployeePerformanceTimelineService(PerformanceServiceSupport):
    def __init__(self, timeline_repository, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.timeline_repository = timeline_repository

    def create_timeline_event(
        self,
        context,
        employee_id,
        event_type,
        event_source,
        source_entity_id,
        lineage_id,
        timeline_event_id=None,
    ):
        context = self.context(context)
        event = EmployeePerformanceTimelineEvent(
            timeline_event_id=timeline_event_id or str(uuid4()),
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            event_type=event_type,
            event_source=PerformanceTimelineEventSource.from_value(
                event_source
            ),
            source_entity_id=source_entity_id,
            lineage_id=lineage_id,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.timeline_repository.save(context, event)
        self.audit(
            context,
            CoachingAuditEvent.TIMELINE_EVENT_CREATED,
            "performance_timeline_event",
            event.timeline_event_id,
            {
                "employee_id": employee_id,
                "event_type": event.event_type,
                "event_source": event.event_source.value,
                "source_entity_id": source_entity_id,
                "lineage_id": lineage_id,
            },
        )
        return event

    def get_timeline(self, context, employee_id):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.VIEW_PERFORMANCE_TIMELINE,
            "performance_timeline",
            employee_id,
        )
        return self.timeline_repository.get_timeline(context, employee_id)
