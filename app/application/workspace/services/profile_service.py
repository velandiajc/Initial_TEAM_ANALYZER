from app.application.workspace.read_models import AgentPerformanceProfileView
from app.application.workspace.rules import WorkspaceAuditEvent
from app.application.workspace.services._support import WorkspaceServiceSupport
from app.core.permissions import WorkspacePermission
from app.domain.performance.value_objects import CommitmentStatus


class SupervisorProfileService(WorkspaceServiceSupport):
    def build_agent_profile(
        self,
        context,
        request,
        kpi_results=(),
        risk_results=(),
        impact_assessments=(),
        priority_assessments=(),
        coaching_sessions=(),
        commitments=(),
        evidence_references=(),
        timeline_preview=(),
        employee_display_name=None,
    ):
        context = self.authorize(
            context,
            request,
            WorkspacePermission.VIEW_AGENT_PERFORMANCE_PROFILE,
            "agent_performance_profile",
            request.employee_id,
        )
        groups = tuple(
            tuple(group)
            for group in (
                kpi_results,
                risk_results,
                impact_assessments,
                priority_assessments,
                coaching_sessions,
                commitments,
            )
        )
        records = tuple(
            item
            for group in groups
            for item in group
        )
        self.require_tenant(
            context,
            records,
            "agent_performance_profile",
            request.employee_id,
        )
        employee_id = request.employee_id
        kpis = [
            item
            for item in groups[0]
            if self._result_employee(item) == employee_id
        ]
        risks = [
            item for item in groups[1]
            if item.entity_id == employee_id
        ]
        impacts = [
            item for item in groups[2]
            if item.entity_id == employee_id
        ]
        priorities = [
            item for item in groups[3]
            if item.entity_id == employee_id
        ]
        sessions = [
            item for item in groups[4]
            if item.employee_id == employee_id
        ]
        employee_commitments = [
            item for item in groups[5]
            if item.employee_id == employee_id
        ]
        latest_risk = self._latest(risks, "assessed_at")
        latest_impact = self._latest(impacts, "created_at")
        latest_priority = self._latest(priorities, "created_at")
        if not latest_priority or not latest_impact or not latest_risk:
            raise ValueError(
                "Agent profile requires governed Risk, Impact, and Priority."
            )
        priority_references = self.lineage.priority_references(
            latest_priority,
            latest_impact,
        )
        risk_references = [
            f"risk_lineage:{latest_risk.lineage_id}",
            f"risk_result:{latest_risk.result_id}",
            *(
                f"kpi_result:{result_id}"
                for result_id in latest_risk.kpi_result_ids
            ),
            *(
                "formula_version:"
                f"{item.get('formula_version_id', '')}:"
                f"{item.get('formula_version_number', '')}"
                for item in latest_risk.formula_versions
            ),
        ]
        kpi_summary = []
        kpi_references = []
        for result in sorted(
            kpis,
            key=lambda item: (item.kpi_id, item.calculated_at),
        ):
            lineage = result.metadata.get("lineage_id", ())
            if isinstance(lineage, str):
                lineage = (lineage,)
            if not lineage:
                raise ValueError("KPI Result lineage is required.")
            kpi_references.extend(
                f"kpi_lineage:{value}"
                for value in lineage
            )
            kpi_references.append(f"kpi_result:{result.result_id}")
            kpi_summary.append({
                "result_id": result.result_id,
                "kpi_id": result.kpi_id,
                "value": result.value,
                "status": result.status.value,
                "data_quality_status": result.data_quality_status,
                "formula_version_id": result.formula_version_id,
                "formula_version_number": result.formula_version_number,
            })
        safe_evidence, reasons = self.suppression.filter_references(
            tuple(evidence_references)
            + tuple(
                session.evidence_pack_id
                for session in sessions
            )
            + tuple(
                artifact_id
                for session in sessions
                for artifact_id in session.evidence_artifact_ids_snapshot
            )
        )
        display_name, name_reasons = self.suppression.suppress(
            employee_display_name or employee_id
        )
        timeline, timeline_reasons = self.suppression.suppress(
            tuple(timeline_preview)
        )
        priority_reason, priority_reasons = self.suppression.suppress(
            latest_priority.priority_reason
        )
        all_reasons = (
            reasons
            + name_reasons
            + timeline_reasons
            + priority_reasons
        )
        self.audit_suppression(
            context,
            "agent_performance_profile",
            employee_id,
            all_reasons,
        )
        open_commitments = tuple({
            "commitment_id": item.commitment_id,
            "session_id": item.session_id,
            "target_date": item.target_date.isoformat(),
            "status": item.status.value,
            "lineage_id": item.lineage_id,
        } for item in employee_commitments if item.status in {
            CommitmentStatus.OPEN,
            CommitmentStatus.IN_PROGRESS,
        })
        lineage = self.lineage.collect(
            priority_references,
            risk_references,
            kpi_references,
            (
                f"coaching_lineage:{session.lineage_id}"
                for session in sessions
            ),
            (
                f"commitment_lineage:{item.lineage_id}"
                for item in employee_commitments
            ),
            (
                f"evidence_reference:{reference}"
                for reference in safe_evidence
            ),
        )
        view = AgentPerformanceProfileView(
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            employee_display_name=display_name,
            risk_summary={
                "result_id": latest_risk.result_id,
                "risk_score": latest_risk.risk_score,
                "risk_level": latest_risk.risk_level.value,
                "risk_definition_version": (
                    latest_risk.risk_definition_version
                ),
                "risk_rule_version": latest_risk.rule_version_number,
            },
            impact_summary={
                "impact_assessment_id": (
                    latest_impact.impact_assessment_id
                ),
                "impact_score": latest_impact.impact_score,
                "impact_level": latest_impact.impact_level.value,
                "impact_definition_version": (
                    latest_impact.impact_definition_version
                ),
                "impact_factor_versions": dict(
                    latest_impact.impact_factor_versions
                ),
            },
            priority_summary={
                "priority_assessment_id": (
                    latest_priority.priority_assessment_id
                ),
                "priority_score": latest_priority.priority_score,
                "priority_level": latest_priority.priority_level.value,
                "priority_reason": priority_reason,
            },
            kpi_summary=tuple(kpi_summary),
            evidence_references=safe_evidence,
            coaching_summary={
                "session_count": len(sessions),
                "latest_session_date": (
                    max(item.created_at for item in sessions).isoformat()
                    if sessions else None
                ),
                "open_commitments_count": len(open_commitments),
            },
            open_commitments=open_commitments,
            timeline_preview=tuple(timeline),
            lineage_references=lineage,
        )
        self.audit(
            context,
            WorkspaceAuditEvent.AGENT_PROFILE_VIEWED,
            "agent_performance_profile",
            employee_id,
            {
                "employee_id": employee_id,
                "lineage_references": list(lineage),
            },
        )
        return view

    def _result_employee(self, result):
        return (
            result.scope.get("employee_id")
            or result.scope.get("agent_id")
            or result.scope.get("entity_id")
        )

    def _latest(self, records, field_name):
        return max(
            records,
            key=lambda item: getattr(item, field_name),
            default=None,
        )
