from collections import Counter
from datetime import date

from app.application.workspace.read_models import (
    SupervisorCommandCenterView,
    TeamPerformanceView,
)
from app.application.workspace.rules import WorkspaceAuditEvent
from app.application.workspace.services._support import WorkspaceServiceSupport
from app.core.permissions import WorkspacePermission
from app.domain.performance.value_objects import (
    CommitmentStatus,
    FollowUpStatus,
)


class SupervisorWorkspaceService(WorkspaceServiceSupport):
    def __init__(
        self,
        audit_service,
        priority_queue_service,
        profile_service=None,
        timeline_service=None,
        coaching_service=None,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.priority_queue_service = priority_queue_service
        self.profile_service = profile_service
        self.timeline_service = timeline_service
        self.coaching_service = coaching_service

    def build_command_center(
        self,
        context,
        request,
        priority_assessments,
        impact_assessments,
        employee_display_names=None,
        risk_drivers=None,
        commitments=(),
        followups=(),
        coaching_sessions=(),
    ):
        context = self.authorize(
            context,
            request,
            WorkspacePermission.VIEW_SUPERVISOR_WORKSPACE,
            "supervisor_command_center",
            request.supervisor_id,
        )
        commitments = tuple(commitments)
        followups = tuple(followups)
        coaching_sessions = tuple(coaching_sessions)
        queue = self.priority_queue_service.build_priority_queue(
            context,
            request,
            priority_assessments,
            impact_assessments,
            employee_display_names,
            risk_drivers,
            commitments,
            coaching_sessions,
        )
        grouped = self.priority_queue_service.group_by_priority_level(queue)
        impact_driver_counts = Counter(
            driver
            for item in queue
            for driver in item.impact_drivers
        )
        open_commitments = [
            item for item in commitments
            if item.status in {
                CommitmentStatus.OPEN,
                CommitmentStatus.IN_PROGRESS,
            }
        ]
        overdue_commitment_ids = {
            item.commitment_id
            for item in open_commitments
            if item.target_date < date.today()
        }
        overdue_followups = [
            item for item in followups
            if item.status == FollowUpStatus.SCHEDULED
            and item.commitment_id in overdue_commitment_ids
        ]
        lineage = (
            self.lineage.collect(*(
                item.lineage_references
                for item in queue
            ))
            if queue
            else ("workspace_status:incomplete:no_results",)
        )
        view = SupervisorCommandCenterView(
            tenant_id=context.tenant_id,
            supervisor_id=request.supervisor_id,
            priority_queue=queue,
            team_health_summary={
                "employee_count": len(queue),
                "lineage_complete": bool(queue),
                "priority_distribution": {
                    level: len(items)
                    for level, items in grouped.items()
                },
            },
            immediate_intervention_count=len(
                grouped["IMMEDIATE_INTERVENTION"]
            ),
            escalate_count=len(grouped["ESCALATE"]),
            coach_count=len(grouped["COACH"]),
            monitor_count=len(grouped["MONITOR"]),
            top_operational_impact_drivers=tuple(
                driver
                for driver, _ in impact_driver_counts.most_common(3)
            ),
            open_commitments_count=len(open_commitments),
            overdue_followups_count=len(overdue_followups),
            lineage_references=lineage,
        )
        self.audit(
            context,
            WorkspaceAuditEvent.SUPERVISOR_WORKSPACE_VIEWED,
            "supervisor_command_center",
            request.supervisor_id,
            {
                "supervisor_id": request.supervisor_id,
                "lineage_references": list(lineage),
            },
        )
        return view

    def build_team_performance(
        self,
        context,
        request,
        priority_assessments,
        impact_assessments,
        kpi_results=(),
        risk_results=(),
        commitments=(),
        coaching_sessions=(),
        employee_display_names=None,
    ):
        context = self.authorize(
            context,
            request,
            WorkspacePermission.VIEW_TEAM_PERFORMANCE_WORKSPACE,
            "team_performance_view",
            request.team_id,
        )
        priority_assessments = tuple(priority_assessments)
        impact_assessments = tuple(impact_assessments)
        kpi_results = tuple(kpi_results)
        risk_results = tuple(risk_results)
        commitments = tuple(commitments)
        coaching_sessions = tuple(coaching_sessions)
        queue = self.priority_queue_service.build_priority_queue(
            context,
            request,
            priority_assessments,
            impact_assessments,
            employee_display_names,
            commitments=commitments,
            coaching_sessions=coaching_sessions,
        )
        employee_ids = set(request.employee_ids)
        self.require_tenant(
            context,
            tuple(kpi_results) + tuple(risk_results),
            "team_performance_view",
            request.team_id,
        )
        impact_by_id = {
            item.impact_assessment_id: item
            for item in impact_assessments
        }
        latest_priority_by_employee = {}
        for item in priority_assessments:
            if employee_ids and item.entity_id not in employee_ids:
                continue
            current = latest_priority_by_employee.get(item.entity_id)
            if current is None or item.created_at > current.created_at:
                latest_priority_by_employee[item.entity_id] = item
        impact_distribution = Counter(
            impact_by_id[item.impact_assessment_id].impact_level.value
            for item in latest_priority_by_employee.values()
            if item.impact_assessment_id in impact_by_id
        )
        latest_risk_by_employee = {}
        for item in risk_results:
            if employee_ids and item.entity_id not in employee_ids:
                continue
            current = latest_risk_by_employee.get(item.entity_id)
            if current is None or item.assessed_at > current.assessed_at:
                latest_risk_by_employee[item.entity_id] = item
        risk_distribution = Counter(
            item.risk_level.value
            for item in latest_risk_by_employee.values()
        )
        priority_distribution = Counter(
            item.priority_level
            for item in queue
        )
        kpi_summary = []
        kpi_lineage = []
        for result in kpi_results:
            employee_id = (
                result.scope.get("employee_id")
                or result.scope.get("agent_id")
            )
            if employee_ids and employee_id not in employee_ids:
                continue
            lineage = result.metadata.get("lineage_id", ())
            if isinstance(lineage, str):
                lineage = (lineage,)
            if not lineage:
                raise ValueError("Team KPI Result lineage is required.")
            kpi_lineage.extend(
                f"kpi_lineage:{value}"
                for value in lineage
            )
            kpi_summary.append({
                "employee_id": employee_id,
                "result_id": result.result_id,
                "kpi_id": result.kpi_id,
                "value": result.value,
                "status": result.status.value,
                "formula_version_number": (
                    result.formula_version_number
                ),
            })
        lineage_groups = [
            item.lineage_references
            for item in queue
        ]
        lineage_groups.extend((
            kpi_lineage,
            tuple(
                f"risk_lineage:{item.lineage_id}"
                for item in latest_risk_by_employee.values()
            ),
        ))
        lineage = (
            self.lineage.collect(*lineage_groups)
            if any(lineage_groups)
            else ("workspace_status:incomplete:no_results",)
        )
        view = TeamPerformanceView(
            tenant_id=context.tenant_id,
            team_id=request.team_id,
            supervisor_id=request.supervisor_id,
            employees=tuple({
                "employee_id": item.employee_id,
                "employee_display_name": item.employee_display_name,
                "priority_level": item.priority_level,
                "priority_score": item.priority_score,
                "risk_score": item.risk_score,
                "impact_score": item.impact_score,
                "open_commitments_count": (
                    item.open_commitments_count
                ),
            } for item in queue),
            risk_distribution=dict(risk_distribution),
            impact_distribution=dict(impact_distribution),
            priority_distribution=dict(priority_distribution),
            team_kpi_summary=tuple(kpi_summary),
            team_coaching_summary={
                "session_count": sum(
                    1 for item in coaching_sessions
                    if not employee_ids
                    or item.employee_id in employee_ids
                ),
                "open_commitments_count": sum(
                    item.open_commitments_count
                    for item in queue
                ),
            },
            lineage_references=lineage,
        )
        self.audit(
            context,
            WorkspaceAuditEvent.TEAM_PERFORMANCE_VIEWED,
            "team_performance_view",
            request.team_id,
            {
                "team_id": request.team_id,
                "supervisor_id": request.supervisor_id,
                "lineage_references": list(lineage),
            },
        )
        return view

    def build_agent_profile(self, *args, **kwargs):
        if self.profile_service is None:
            raise RuntimeError("SupervisorProfileService is required.")
        return self.profile_service.build_agent_profile(*args, **kwargs)

    def build_employee_timeline(self, *args, **kwargs):
        if self.timeline_service is None:
            raise RuntimeError("SupervisorTimelineService is required.")
        return self.timeline_service.build_timeline(*args, **kwargs)

    def build_coaching_workspace(self, *args, **kwargs):
        if self.coaching_service is None:
            raise RuntimeError(
                "SupervisorCoachingWorkspaceService is required."
            )
        return self.coaching_service.build_coaching_workspace(
            *args,
            **kwargs,
        )
