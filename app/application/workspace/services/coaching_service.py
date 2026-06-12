from app.application.workspace.read_models import CoachingWorkspaceView
from app.application.workspace.rules import WorkspaceAuditEvent
from app.application.workspace.services._support import WorkspaceServiceSupport
from app.core.permissions import WorkspacePermission
from app.domain.performance.value_objects import CoachingNoteVisibility


class SupervisorCoachingWorkspaceService(WorkspaceServiceSupport):
    def build_coaching_workspace(
        self,
        context,
        request,
        priority_assessment,
        impact_assessment,
        opportunities=(),
        coaching_sessions=(),
        commitments=(),
        followups=(),
        notes=(),
        evidence_references=(),
    ):
        context = self.authorize(
            context,
            request,
            WorkspacePermission.VIEW_COACHING_WORKSPACE,
            "coaching_workspace_view",
            request.employee_id,
        )
        records = (
            priority_assessment,
            impact_assessment,
            *tuple(opportunities),
            *tuple(coaching_sessions),
            *tuple(commitments),
            *tuple(followups),
            *tuple(notes),
        )
        self.require_tenant(
            context,
            records,
            "coaching_workspace_view",
            request.employee_id,
        )
        if (
            priority_assessment.entity_id != request.employee_id
            or impact_assessment.entity_id != request.employee_id
        ):
            raise PermissionError("Coaching workspace employee mismatch.")
        priority_lineage = self.lineage.priority_references(
            priority_assessment,
            impact_assessment,
        )
        sessions = tuple(
            item for item in coaching_sessions
            if item.employee_id == request.employee_id
        )
        session_ids = {
            item.coaching_session_id
            for item in sessions
        }
        employee_opportunities = tuple(
            item for item in opportunities
            if item.employee_id == request.employee_id
        )
        employee_commitments = tuple(
            item for item in commitments
            if item.employee_id == request.employee_id
        )
        employee_followups = tuple(
            item for item in followups
            if item.session_id in session_ids
        )
        visible_notes = []
        private_note_access = False
        for note in notes:
            if note.session_id not in session_ids:
                continue
            if self.visibility.can_view_note(
                context,
                note.visibility_level,
            ):
                visible_notes.append({
                    "note_id": note.note_id,
                    "visibility_level": note.visibility_level.value,
                    "lineage_id": note.lineage_id,
                })
                if (
                    note.visibility_level
                    != CoachingNoteVisibility.SHARED
                ):
                    private_note_access = True
                continue
            event = (
                WorkspaceAuditEvent.LEADERSHIP_NOTE_ACCESS_DENIED
                if (
                    note.visibility_level
                    == CoachingNoteVisibility.LEADERSHIP_ONLY
                )
                else WorkspaceAuditEvent.PRIVATE_NOTE_ACCESS_DENIED
            )
            self.audit(
                context,
                event,
                "coaching_note",
                note.note_id,
                {
                    "employee_id": request.employee_id,
                    "permission": (
                        WorkspacePermission.VIEW_LEADERSHIP_NOTES.value
                        if event == (
                            WorkspaceAuditEvent
                            .LEADERSHIP_NOTE_ACCESS_DENIED
                        )
                        else (
                            WorkspacePermission
                            .VIEW_PRIVATE_COACHING_NOTES.value
                        )
                    ),
                    "suppression_reason_code": (
                        "NOTE_VISIBILITY_DENIED"
                    ),
                },
            )
        safe_evidence, reasons = self.suppression.filter_references(
            tuple(evidence_references)
            + tuple(
                item.evidence_pack_id
                for item in sessions
            )
            + tuple(
                artifact_id
                for item in sessions
                for artifact_id in item.evidence_artifact_ids_snapshot
            )
        )
        self.audit_suppression(
            context,
            "coaching_workspace_view",
            request.employee_id,
            reasons,
        )
        priority_reason, reason_suppressions = self.suppression.suppress(
            priority_assessment.priority_reason
        )
        self.audit_suppression(
            context,
            "coaching_workspace_view",
            request.employee_id,
            reason_suppressions,
        )
        lineage = self.lineage.collect(
            priority_lineage,
            (
                f"opportunity_lineage:{item.lineage_id}"
                for item in employee_opportunities
            ),
            (
                f"coaching_lineage:{item.lineage_id}"
                for item in sessions
            ),
            (
                f"commitment_lineage:{item.lineage_id}"
                for item in employee_commitments
            ),
            (
                f"followup_lineage:{item.lineage_id}"
                for item in employee_followups
            ),
            (
                f"note_lineage:{item['lineage_id']}"
                for item in visible_notes
            ),
            (
                f"evidence_reference:{reference}"
                for reference in safe_evidence
            ),
        )
        view = CoachingWorkspaceView(
            tenant_id=context.tenant_id,
            employee_id=request.employee_id,
            coaching_context={
                "sessions": tuple({
                    "coaching_session_id": item.coaching_session_id,
                    "status": item.status.value,
                    "coaching_version": item.coaching_version,
                    "created_at": item.created_at,
                    "lineage_id": item.lineage_id,
                } for item in sessions),
                "visible_notes": tuple(visible_notes),
            },
            linked_priority_assessment={
                "priority_assessment_id": (
                    priority_assessment.priority_assessment_id
                ),
                "priority_score": priority_assessment.priority_score,
                "priority_level": priority_assessment.priority_level.value,
                "priority_reason": priority_reason,
                "lineage_id": priority_assessment.lineage_id,
            },
            linked_impact_assessment={
                "impact_assessment_id": (
                    impact_assessment.impact_assessment_id
                ),
                "impact_score": impact_assessment.impact_score,
                "impact_level": impact_assessment.impact_level.value,
                "lineage_id": impact_assessment.lineage_id,
            },
            linked_evidence_references=safe_evidence,
            opportunities=tuple({
                "opportunity_id": item.opportunity_id,
                "opportunity_type": item.opportunity_type,
                "status": item.status.value,
                "evidence_pack_id": item.evidence_pack_id,
                "risk_result_id": item.risk_result_id,
                "lineage_id": item.lineage_id,
            } for item in employee_opportunities),
            commitments=tuple({
                "commitment_id": item.commitment_id,
                "session_id": item.session_id,
                "target_date": item.target_date.isoformat(),
                "status": item.status.value,
                "lineage_id": item.lineage_id,
            } for item in employee_commitments),
            followups=tuple({
                "followup_id": item.followup_id,
                "session_id": item.session_id,
                "commitment_id": item.commitment_id,
                "status": item.status.value,
                "lineage_id": item.lineage_id,
            } for item in employee_followups),
            private_note_access=private_note_access,
            lineage_references=lineage,
        )
        self.audit(
            context,
            WorkspaceAuditEvent.COACHING_WORKSPACE_VIEWED,
            "coaching_workspace_view",
            request.employee_id,
            {
                "employee_id": request.employee_id,
                "lineage_references": list(lineage),
            },
        )
        return view
