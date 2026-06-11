from uuid import uuid4

from app.application.performance.services._service import (
    PerformanceServiceSupport,
)
from app.core.permissions import CoachingPermission
from app.domain.performance.entities import CoachingCommitment
from app.domain.performance.value_objects import (
    CoachingAuditEvent,
    CommitmentStatus,
    PerformanceTimelineEventSource,
)


class CoachingCommitmentService(PerformanceServiceSupport):
    def __init__(
        self,
        commitment_repository,
        session_repository,
        timeline_service,
        audit_service,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.commitment_repository = commitment_repository
        self.session_repository = session_repository
        self.timeline_service = timeline_service

    def create_commitment(
        self,
        context,
        session_id,
        description,
        target_date,
        commitment_id=None,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.CREATE_COMMITMENT,
            "coaching_commitment",
            commitment_id or "new",
        )
        session = self.require_entity(
            context,
            self.session_repository.get_session(context, session_id),
            "coaching_session",
            session_id,
        )
        commitment = CoachingCommitment(
            commitment_id=commitment_id or str(uuid4()),
            tenant_id=context.tenant_id,
            session_id=session_id,
            employee_id=session.employee_id,
            description=description,
            target_date=target_date,
            lineage_id=session.lineage_id,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.commitment_repository.save(context, commitment)
        self.audit(
            context,
            CoachingAuditEvent.COMMITMENT_CREATED,
            "coaching_commitment",
            commitment.commitment_id,
            self._metadata(commitment),
        )
        self._timeline(context, commitment)
        return commitment

    def update_commitment_status(self, context, commitment_id, status):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.UPDATE_COMMITMENT,
            "coaching_commitment",
            commitment_id,
        )
        commitment = self.require_entity(
            context,
            self.commitment_repository.get_by_id(context, commitment_id),
            "coaching_commitment",
            commitment_id,
        )
        try:
            updated = commitment.with_status(status, context.user_id)
            self.commitment_repository.save(context, updated)
            action = {
                CommitmentStatus.COMPLETED: (
                    CoachingAuditEvent.COMMITMENT_COMPLETED
                ),
                CommitmentStatus.MISSED: CoachingAuditEvent.COMMITMENT_MISSED,
            }.get(updated.status)
            if action:
                self.audit(
                    context,
                    action,
                    "coaching_commitment",
                    commitment_id,
                    self._metadata(updated),
                )
            self._timeline(context, updated)
            return updated
        except (PermissionError, ValueError) as exc:
            self.audit_modification_rejected(
                context,
                "coaching_commitment",
                commitment_id,
                exc,
            )
            raise

    def _timeline(self, context, commitment):
        self.timeline_service.create_timeline_event(
            context,
            commitment.employee_id,
            f"COMMITMENT_{commitment.status.value}",
            PerformanceTimelineEventSource.COMMITMENT,
            commitment.commitment_id,
            commitment.lineage_id,
        )

    def _metadata(self, commitment):
        return {
            "session_id": commitment.session_id,
            "employee_id": commitment.employee_id,
            "status": commitment.status.value,
            "lineage_id": commitment.lineage_id,
            "target_date": commitment.target_date.isoformat(),
        }
