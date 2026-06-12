from collections import OrderedDict

from app.application.workspace.read_models import SupervisorPriorityQueueItem
from app.application.workspace.rules import WorkspaceAuditEvent
from app.application.workspace.services._support import WorkspaceServiceSupport
from app.core.permissions import WorkspacePermission
from app.domain.performance.value_objects import CommitmentStatus


class SupervisorPriorityQueueService(WorkspaceServiceSupport):
    LEVEL_ORDER = (
        "IMMEDIATE_INTERVENTION",
        "ESCALATE",
        "COACH",
        "MONITOR",
    )

    def build_priority_queue(
        self,
        context,
        request,
        priority_assessments,
        impact_assessments,
        employee_display_names=None,
        risk_drivers=None,
        commitments=(),
        coaching_sessions=(),
    ):
        context = self.authorize(
            context,
            request,
            WorkspacePermission.VIEW_SUPERVISOR_PRIORITY_QUEUE,
            "supervisor_priority_queue",
            request.supervisor_id,
        )
        priorities = tuple(priority_assessments)
        impacts = tuple(impact_assessments)
        commitments = tuple(commitments)
        coaching_sessions = tuple(coaching_sessions)
        self.require_tenant(
            context,
            priorities + impacts + commitments + coaching_sessions,
            "supervisor_priority_queue",
            request.supervisor_id,
        )
        employee_display_names = employee_display_names or {}
        risk_drivers = risk_drivers or {}
        impacts_by_id = {
            item.impact_assessment_id: item
            for item in impacts
        }
        employee_ids = tuple(
            getattr(request, "employee_ids", ())
            or request.filters.employee_ids
        )
        latest_by_employee = {}
        for priority in priorities:
            if employee_ids and priority.entity_id not in employee_ids:
                continue
            current = latest_by_employee.get(priority.entity_id)
            if current is None or priority.created_at > current.created_at:
                latest_by_employee[priority.entity_id] = priority

        items = []
        suppression_reasons = set()
        for priority in latest_by_employee.values():
            impact = impacts_by_id.get(priority.impact_assessment_id)
            if impact is None:
                raise ValueError(
                    "Priority queue requires its linked impact assessment."
                )
            references = self.lineage.priority_references(priority, impact)
            display_name, reasons = self.suppression.suppress(
                employee_display_names.get(
                    priority.entity_id,
                    priority.entity_id,
                )
            )
            suppression_reasons.update(reasons)
            reason, reasons = self.suppression.suppress(
                priority.priority_reason
            )
            suppression_reasons.update(reasons)
            safe_risk_drivers, reasons = self.suppression.suppress(
                tuple(risk_drivers.get(priority.risk_result_id, ()))
            )
            suppression_reasons.update(reasons)
            sessions = [
                session
                for session in coaching_sessions
                if session.employee_id == priority.entity_id
            ]
            open_commitments = [
                commitment
                for commitment in commitments
                if commitment.employee_id == priority.entity_id
                and commitment.status in {
                    CommitmentStatus.OPEN,
                    CommitmentStatus.IN_PROGRESS,
                }
            ]
            safe_evidence, reasons = self.suppression.filter_references(
                tuple(
                    session.evidence_pack_id
                    for session in sessions
                )
                + tuple(
                    artifact_id
                    for session in sessions
                    for artifact_id in (
                        session.evidence_artifact_ids_snapshot
                    )
                )
            )
            suppression_reasons.update(reasons)
            factor_scores = sorted(
                impact.factor_score_snapshots.items(),
                key=lambda item: (-float(item[1]), item[0]),
            )
            items.append(SupervisorPriorityQueueItem(
                tenant_id=context.tenant_id,
                employee_id=priority.entity_id,
                employee_display_name=display_name,
                priority_level=priority.priority_level.value,
                priority_score=priority.priority_score,
                risk_score=priority.risk_score_snapshot,
                impact_score=priority.impact_score_snapshot,
                risk_drivers=tuple(
                    item for item in safe_risk_drivers
                    if item != "[SUPPRESSED]"
                ),
                impact_drivers=tuple(
                    factor_id
                    for factor_id, _ in factor_scores[:3]
                ),
                priority_reason=reason,
                recommended_action_type=priority.priority_level.value,
                last_coaching_date=(
                    max(session.created_at for session in sessions)
                    if sessions
                    else None
                ),
                open_commitments_count=len(open_commitments),
                lineage_id=priority.lineage_id,
                lineage_references=self.lineage.collect(
                    references,
                    (
                        f"evidence_reference:{reference}"
                        for reference in safe_evidence
                    ),
                ),
            ))
        items.sort(
            key=lambda item: (
                -item.priority_score,
                item.employee_id,
            )
        )
        self.audit_suppression(
            context,
            "supervisor_priority_queue",
            request.supervisor_id,
            suppression_reasons,
        )
        self.audit(
            context,
            WorkspaceAuditEvent.SUPERVISOR_PRIORITY_QUEUE_VIEWED,
            "supervisor_priority_queue",
            request.supervisor_id,
            {
                "supervisor_id": request.supervisor_id,
                "lineage_references": list(
                    self.lineage.collect(*(
                        item.lineage_references
                        for item in items
                    ))
                ) if items else [],
            },
        )
        return tuple(items)

    def group_by_priority_level(self, items):
        grouped = OrderedDict(
            (level, [])
            for level in self.LEVEL_ORDER
        )
        for item in items:
            grouped.setdefault(item.priority_level, []).append(item)
        return {
            level: tuple(sorted(
                values,
                key=lambda item: (-item.priority_score, item.employee_id),
            ))
            for level, values in grouped.items()
        }
