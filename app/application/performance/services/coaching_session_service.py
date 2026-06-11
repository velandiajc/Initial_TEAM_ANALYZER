from uuid import uuid4

from app.application.performance.services._service import (
    PerformanceServiceSupport,
)
from app.application.performance.services.coaching_lineage_service import (
    CoachingLineageService,
)
from app.core.permissions import CoachingPermission
from app.domain.performance.entities import CoachingSession
from app.domain.performance.value_objects import (
    CoachingAuditEvent,
    CoachingSessionStatus,
    PerformanceOpportunityStatus,
    PerformanceTimelineEventSource,
)


class CoachingSessionService(PerformanceServiceSupport):
    def __init__(
        self,
        session_repository,
        opportunity_repository,
        timeline_service,
        audit_service,
        lineage_service=None,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.session_repository = session_repository
        self.opportunity_repository = opportunity_repository
        self.timeline_service = timeline_service
        self.lineage_service = lineage_service or CoachingLineageService()

    def create_session(
        self,
        context,
        employee_id,
        session_owner_id,
        performance_opportunity_id,
        evidence_pack,
        risk_result,
        coaching_version,
        session_id=None,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.CREATE_COACHING_SESSION,
            "coaching_session",
            session_id or "new",
        )
        opportunity = self.require_entity(
            context,
            self.opportunity_repository.get_by_id(
                context,
                performance_opportunity_id,
            ),
            "performance_opportunity",
            performance_opportunity_id,
        )
        if opportunity.status != PerformanceOpportunityStatus.ACCEPTED:
            raise ValueError(
                "Performance opportunity must be accepted before session "
                "creation."
            )
        if opportunity.employee_id != employee_id:
            raise ValueError("Opportunity employee does not match session.")
        if opportunity.evidence_pack_id != evidence_pack.evidence_pack_id:
            raise ValueError("Opportunity evidence pack does not match session.")
        if opportunity.risk_result_id != risk_result.result_id:
            raise ValueError("Opportunity risk result does not match session.")

        snapshot = self.lineage_service.build_snapshot(
            context.tenant_id,
            employee_id,
            evidence_pack,
            risk_result,
        )
        if snapshot.lineage_id != opportunity.lineage_id:
            raise ValueError("Opportunity lineage does not match session lineage.")

        session = CoachingSession(
            coaching_session_id=session_id or str(uuid4()),
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            session_owner_id=session_owner_id,
            performance_opportunity_id=performance_opportunity_id,
            evidence_pack_id=snapshot.evidence_pack_id,
            evidence_version_snapshot=snapshot.evidence_version_snapshot,
            evidence_artifact_ids_snapshot=(
                snapshot.evidence_artifact_ids_snapshot
            ),
            risk_result_id=snapshot.risk_result_id,
            risk_score_snapshot=snapshot.risk_score_snapshot,
            risk_level_snapshot=snapshot.risk_level_snapshot,
            risk_classification_snapshot=(
                snapshot.risk_classification_snapshot
            ),
            risk_definition_version=snapshot.risk_definition_version,
            risk_rule_version=snapshot.risk_rule_version,
            coaching_version=coaching_version,
            lineage_id=snapshot.lineage_id,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.session_repository.save(context, session)
        self.audit(
            context,
            CoachingAuditEvent.COACHING_SESSION_CREATED,
            "coaching_session",
            session.coaching_session_id,
            self._session_metadata(session),
        )
        self.timeline_service.create_timeline_event(
            context,
            employee_id,
            "COACHING_SESSION_CREATED",
            PerformanceTimelineEventSource.COACHING,
            session.coaching_session_id,
            session.lineage_id,
        )
        return session

    def get_session(self, context, session_id):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.VIEW_COACHING_SESSION,
            "coaching_session",
            session_id,
        )
        return self.require_entity(
            context,
            self.session_repository.get_session(context, session_id),
            "coaching_session",
            session_id,
        )

    def update_session(self, context, session_id, status):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.EDIT_COACHING_SESSION,
            "coaching_session",
            session_id,
        )
        session = self.require_entity(
            context,
            self.session_repository.get_session(context, session_id),
            "coaching_session",
            session_id,
        )
        try:
            updated = session.with_status(status, context.user_id)
            self.session_repository.save(context, updated)
            self.audit(
                context,
                CoachingAuditEvent.COACHING_SESSION_UPDATED,
                "coaching_session",
                session_id,
                self._session_metadata(updated),
            )
            if updated.status in {
                CoachingSessionStatus.COMPLETED,
                CoachingSessionStatus.CANCELLED,
            }:
                self.audit(
                    context,
                    CoachingAuditEvent.COACHING_SESSION_CLOSED,
                    "coaching_session",
                    session_id,
                    self._session_metadata(updated),
                )
            self.timeline_service.create_timeline_event(
                context,
                updated.employee_id,
                f"COACHING_SESSION_{updated.status.value}",
                PerformanceTimelineEventSource.COACHING,
                updated.coaching_session_id,
                updated.lineage_id,
            )
            return updated
        except (PermissionError, ValueError) as exc:
            self.audit_modification_rejected(
                context,
                "coaching_session",
                session_id,
                exc,
            )
            raise

    def close_session(self, context, session_id):
        return self.update_session(
            context,
            session_id,
            CoachingSessionStatus.COMPLETED,
        )

    def _session_metadata(self, session):
        return {
            "employee_id": session.employee_id,
            "performance_opportunity_id": (
                session.performance_opportunity_id
            ),
            "evidence_pack_id": session.evidence_pack_id,
            "risk_result_id": session.risk_result_id,
            "lineage_id": session.lineage_id,
            "status": session.status.value,
            "coaching_version": session.coaching_version,
        }
