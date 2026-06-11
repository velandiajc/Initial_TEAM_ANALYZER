from uuid import uuid4

from app.application.performance.services._service import (
    PerformanceServiceSupport,
)
from app.core.permissions import CoachingPermission
from app.domain.performance.entities import CoachingFollowUp
from app.domain.performance.value_objects import (
    CoachingAuditEvent,
    PerformanceTimelineEventSource,
)


class CoachingFollowUpService(PerformanceServiceSupport):
    def __init__(
        self,
        followup_repository,
        commitment_repository,
        session_repository,
        timeline_service,
        audit_service,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.followup_repository = followup_repository
        self.commitment_repository = commitment_repository
        self.session_repository = session_repository
        self.timeline_service = timeline_service

    def create_followup(
        self,
        context,
        session_id,
        commitment_id,
        reviewer_id,
        followup_id=None,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.CREATE_FOLLOWUP,
            "coaching_followup",
            followup_id or "new",
        )
        session = self.require_entity(
            context,
            self.session_repository.get_session(context, session_id),
            "coaching_session",
            session_id,
        )
        commitment = self.require_entity(
            context,
            self.commitment_repository.get_by_id(context, commitment_id),
            "coaching_commitment",
            commitment_id,
        )
        if commitment.session_id != session.coaching_session_id:
            raise ValueError("Commitment does not belong to coaching session.")
        followup = CoachingFollowUp(
            followup_id=followup_id or str(uuid4()),
            tenant_id=context.tenant_id,
            session_id=session_id,
            commitment_id=commitment_id,
            reviewer_id=reviewer_id,
            outcome="",
            lineage_id=session.lineage_id,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.followup_repository.save(context, followup)
        self.audit(
            context,
            CoachingAuditEvent.FOLLOWUP_CREATED,
            "coaching_followup",
            followup.followup_id,
            self._metadata(followup),
        )
        self._timeline(context, session.employee_id, followup)
        return followup

    def complete_followup(self, context, followup_id, status, outcome):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.CREATE_FOLLOWUP,
            "coaching_followup",
            followup_id,
        )
        followup = self.require_entity(
            context,
            self.followup_repository.get_by_id(context, followup_id),
            "coaching_followup",
            followup_id,
        )
        session = self.require_entity(
            context,
            self.session_repository.get_session(
                context,
                followup.session_id,
            ),
            "coaching_session",
            followup.session_id,
        )
        try:
            updated = followup.with_status(
                status,
                outcome,
                context.user_id,
            )
            self.followup_repository.save(context, updated)
            self._timeline(context, session.employee_id, updated)
            return updated
        except (PermissionError, ValueError) as exc:
            self.audit_modification_rejected(
                context,
                "coaching_followup",
                followup_id,
                exc,
            )
            raise

    def _timeline(self, context, employee_id, followup):
        self.timeline_service.create_timeline_event(
            context,
            employee_id,
            f"FOLLOWUP_{followup.status.value}",
            PerformanceTimelineEventSource.FOLLOWUP,
            followup.followup_id,
            followup.lineage_id,
        )

    def _metadata(self, followup):
        return {
            "session_id": followup.session_id,
            "commitment_id": followup.commitment_id,
            "reviewer_id": followup.reviewer_id,
            "status": followup.status.value,
            "lineage_id": followup.lineage_id,
        }
