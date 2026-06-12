from app.application.operational_impact.services._service import (
    OperationalImpactServiceSupport,
)
from app.core.permissions import OperationalImpactPermission
from app.domain.operational_impact import (
    OperationalImpactAuditEvent,
    OperationalImpactTimelineEvent,
)
from app.domain.operational_impact.entities import new_id
from app.domain.operational_impact.rules import is_material_change


class OperationalImpactTimelineService(OperationalImpactServiceSupport):
    def __init__(self, timeline_repository, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.timeline_repository = timeline_repository

    def create_if_material(
        self,
        context,
        previous_impact,
        previous_priority,
        current_impact,
        current_priority,
    ):
        context = self.context(context)
        if current_priority.entity_type != "employee":
            return None
        if previous_impact is None or previous_priority is None:
            return None
        if not is_material_change(
            previous_impact.impact_level,
            current_impact.impact_level,
            previous_priority.priority_level,
            current_priority.priority_level,
        ):
            return None
        event = OperationalImpactTimelineEvent(
            timeline_event_id=new_id(),
            tenant_id=context.tenant_id,
            employee_id=current_priority.entity_id,
            impact_assessment_id=current_impact.impact_assessment_id,
            priority_assessment_id=current_priority.priority_assessment_id,
            event_type="MATERIAL_OPERATIONAL_IMPACT_CHANGE",
            material_change_reason=(
                f"Impact {previous_impact.impact_level.value} to "
                f"{current_impact.impact_level.value}; priority "
                f"{previous_priority.priority_level.value} to "
                f"{current_priority.priority_level.value}."
            ),
            impact_level_snapshot=current_impact.impact_level,
            priority_level_snapshot=current_priority.priority_level,
            created_by=context.user_id,
        )
        self.timeline_repository.save(context, event)
        self.audit(
            context,
            OperationalImpactAuditEvent.OPERATIONAL_IMPACT_TIMELINE_EVENT_CREATED,
            "operational_impact_timeline_event",
            event.timeline_event_id,
            {
                "employee_id": event.employee_id,
                "impact_assessment_id": event.impact_assessment_id,
                "priority_assessment_id": event.priority_assessment_id,
                "impact_level": event.impact_level_snapshot.value,
                "priority_level": event.priority_level_snapshot.value,
            },
        )
        return event

    def get_timeline(self, context, employee_id):
        context = self.context(context)
        self.require_permission(
            context,
            OperationalImpactPermission.VIEW_RISK_PRIORITY,
            "operational_impact_timeline",
            employee_id,
        )
        return self.timeline_repository.list_for_employee(
            context,
            employee_id,
        )
