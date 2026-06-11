from uuid import uuid4

from app.application.performance.services._service import (
    PerformanceServiceSupport,
)
from app.application.performance.services.coaching_lineage_service import (
    CoachingLineageService,
)
from app.core.permissions import CoachingPermission
from app.domain.performance.entities import PerformanceOpportunity
from app.domain.performance.value_objects import (
    CoachingAuditEvent,
    PerformanceOpportunityStatus,
)


class PerformanceOpportunityService(PerformanceServiceSupport):
    def __init__(
        self,
        opportunity_repository,
        audit_service,
        lineage_service=None,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.opportunity_repository = opportunity_repository
        self.lineage_service = lineage_service or CoachingLineageService()

    def create_opportunity(
        self,
        context,
        employee_id,
        opportunity_type,
        business_reason,
        evidence_pack,
        risk_result,
        owner=None,
        opportunity_id=None,
    ):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.CREATE_COACHING_SESSION,
            "performance_opportunity",
            opportunity_id or "new",
        )
        lineage_id = self.lineage_service.validate_lineage(
            context.tenant_id,
            employee_id,
            evidence_pack,
            risk_result,
        )
        self._reject_duplicate(
            context,
            employee_id,
            evidence_pack.evidence_pack_id,
            risk_result.result_id,
        )
        opportunity = PerformanceOpportunity(
            opportunity_id=opportunity_id or str(uuid4()),
            tenant_id=context.tenant_id,
            employee_id=employee_id,
            opportunity_type=opportunity_type,
            business_reason=business_reason,
            evidence_pack_id=evidence_pack.evidence_pack_id,
            risk_result_id=risk_result.result_id,
            owner=owner or context.user_id,
            lineage_id=lineage_id,
            created_by=context.user_id,
            updated_by=context.user_id,
        )
        self.opportunity_repository.save(context, opportunity)
        self.audit(
            context,
            CoachingAuditEvent.COACHING_OPPORTUNITY_CREATED,
            "performance_opportunity",
            opportunity.opportunity_id,
            {
                "employee_id": employee_id,
                "evidence_pack_id": opportunity.evidence_pack_id,
                "risk_result_id": opportunity.risk_result_id,
                "lineage_id": opportunity.lineage_id,
            },
        )
        return opportunity

    def update_status(self, context, opportunity_id, status):
        context = self.context(context)
        self.require_permission(
            context,
            CoachingPermission.EDIT_COACHING_SESSION,
            "performance_opportunity",
            opportunity_id,
        )
        opportunity = self.require_entity(
            context,
            self.opportunity_repository.get_by_id(context, opportunity_id),
            "performance_opportunity",
            opportunity_id,
        )
        try:
            updated = opportunity.with_status(status, context.user_id)
            self.opportunity_repository.save(context, updated)
            return updated
        except (PermissionError, ValueError) as exc:
            self.audit_modification_rejected(
                context,
                "performance_opportunity",
                opportunity_id,
                exc,
            )
            raise

    def accept_opportunity(self, context, opportunity_id):
        return self.update_status(
            context,
            opportunity_id,
            PerformanceOpportunityStatus.ACCEPTED,
        )

    def close_opportunity(self, context, opportunity_id):
        return self.update_status(
            context,
            opportunity_id,
            PerformanceOpportunityStatus.CLOSED,
        )

    def _reject_duplicate(
        self,
        context,
        employee_id,
        evidence_pack_id,
        risk_result_id,
    ):
        active_statuses = {
            PerformanceOpportunityStatus.IDENTIFIED,
            PerformanceOpportunityStatus.UNDER_REVIEW,
            PerformanceOpportunityStatus.ACCEPTED,
        }
        duplicate = next(
            (
                item
                for item in self.opportunity_repository.list_for_employee(
                    context,
                    employee_id,
                )
                if item.evidence_pack_id == evidence_pack_id
                and item.risk_result_id == risk_result_id
                and item.status in active_statuses
            ),
            None,
        )
        if duplicate:
            raise ValueError(
                "An active opportunity already exists for this evidence "
                "and risk lineage."
            )
