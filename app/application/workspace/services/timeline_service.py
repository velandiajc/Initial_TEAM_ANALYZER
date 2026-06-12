from app.application.workspace.read_models import (
    EmployeePerformanceTimelineView,
)
from app.application.workspace.rules import WorkspaceAuditEvent
from app.application.workspace.services._support import WorkspaceServiceSupport
from app.core.permissions import WorkspacePermission


class SupervisorTimelineService(WorkspaceServiceSupport):
    def build_timeline(
        self,
        context,
        request,
        performance_events=(),
        operational_impact_events=(),
        risk_results=(),
        impact_assessments=(),
        priority_assessments=(),
    ):
        context = self.authorize(
            context,
            request,
            WorkspacePermission.VIEW_EMPLOYEE_TIMELINE,
            "employee_performance_timeline_view",
            request.employee_id,
        )
        groups = tuple(
            tuple(group)
            for group in (
                performance_events,
                operational_impact_events,
                risk_results,
                impact_assessments,
                priority_assessments,
            )
        )
        records = tuple(item for group in groups for item in group)
        self.require_tenant(
            context,
            records,
            "employee_performance_timeline_view",
            request.employee_id,
        )
        events = []
        lineage = []
        employee_id = request.employee_id
        for item in groups[0]:
            if item.employee_id != employee_id:
                continue
            events.append({
                "event_id": item.timeline_event_id,
                "event_type": item.event_type,
                "event_source": item.event_source.value,
                "source_entity_id": item.source_entity_id,
                "occurred_at": item.created_at,
                "lineage_id": item.lineage_id,
            })
            lineage.append(f"performance_lineage:{item.lineage_id}")
        for item in groups[1]:
            if item.employee_id != employee_id:
                continue
            events.append({
                "event_id": item.timeline_event_id,
                "event_type": item.event_type,
                "event_source": "OPERATIONAL_IMPACT",
                "source_entity_id": item.impact_assessment_id,
                "occurred_at": item.created_at,
                "impact_level": item.impact_level_snapshot.value,
                "priority_level": item.priority_level_snapshot.value,
            })
            lineage.extend((
                f"impact_assessment:{item.impact_assessment_id}",
                f"priority_assessment:{item.priority_assessment_id}",
            ))
        for item in groups[2]:
            if item.entity_id != employee_id:
                continue
            events.append({
                "event_id": item.result_id,
                "event_type": "RISK_ASSESSED",
                "event_source": "RISK",
                "source_entity_id": item.result_id,
                "occurred_at": item.assessed_at,
                "risk_score": item.risk_score,
                "risk_level": item.risk_level.value,
                "lineage_id": item.lineage_id,
            })
            lineage.append(f"risk_lineage:{item.lineage_id}")
        for item in groups[3]:
            if item.entity_id != employee_id:
                continue
            events.append({
                "event_id": item.impact_assessment_id,
                "event_type": "OPERATIONAL_IMPACT_ASSESSED",
                "event_source": "OPERATIONAL_IMPACT",
                "source_entity_id": item.impact_assessment_id,
                "occurred_at": item.created_at,
                "impact_score": item.impact_score,
                "impact_level": item.impact_level.value,
                "lineage_id": item.lineage_id,
            })
            lineage.append(f"impact_lineage:{item.lineage_id}")
        for item in groups[4]:
            if item.entity_id != employee_id:
                continue
            events.append({
                "event_id": item.priority_assessment_id,
                "event_type": "RISK_PRIORITY_ASSESSED",
                "event_source": "RISK_PRIORITY",
                "source_entity_id": item.priority_assessment_id,
                "occurred_at": item.created_at,
                "priority_score": item.priority_score,
                "priority_level": item.priority_level.value,
                "lineage_id": item.lineage_id,
            })
            lineage.append(f"priority_lineage:{item.lineage_id}")
        start = request.filters.date_range_start
        end = request.filters.date_range_end
        events = [
            event
            for event in events
            if (start is None or event["occurred_at"] >= start)
            and (end is None or event["occurred_at"] <= end)
        ]
        events.sort(
            key=lambda event: (
                event["occurred_at"],
                event["event_id"],
            )
        )
        sanitized, reasons = self.suppression.suppress(events)
        self.audit_suppression(
            context,
            "employee_performance_timeline_view",
            employee_id,
            reasons,
        )
        references = (
            self.lineage.require(lineage)
            if lineage
            else ("workspace_status:incomplete:no_events",)
        )
        view = EmployeePerformanceTimelineView(
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            events=tuple(sanitized),
            event_count=len(sanitized),
            date_range_start=start,
            date_range_end=end,
            lineage_references=references,
        )
        self.audit(
            context,
            WorkspaceAuditEvent.EMPLOYEE_TIMELINE_VIEWED,
            "employee_performance_timeline_view",
            employee_id,
            {
                "employee_id": employee_id,
                "lineage_references": list(references),
            },
        )
        return view
