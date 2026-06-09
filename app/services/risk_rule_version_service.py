from datetime import datetime

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.risk import RiskRuleVersion


class MissingApprovedActiveRiskRuleError(ValueError):
    pass


class RiskRuleConflictError(ValueError):
    pass


class RiskRuleVersionService:
    def __init__(self, risk_repository):
        self.risk_repository = risk_repository

    def get_approved_active_rule_for_period(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> RiskRuleVersion:
        context = require_tenant_context(context)
        _validate_period(period_start, period_end)

        rules = self.risk_repository.get_approved_active_rules_for_period(
            context,
            risk_definition_id,
            period_start,
            period_end
        )

        if not rules:
            raise MissingApprovedActiveRiskRuleError(
                "No approved active risk rule found for risk definition in period."
            )

        if len(rules) > 1:
            raise RiskRuleConflictError(
                "Multiple approved active risk rules found for risk definition in period."
            )

        return rules[0]

    def get_rule_lineage(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> list[RiskRuleVersion]:
        context = require_tenant_context(context)

        return self.risk_repository.get_rule_lineage(
            context,
            risk_definition_id
        )

    def validate_no_active_period_conflict(
        self,
        context: TenantContext | None,
        rule_version: RiskRuleVersion
    ) -> None:
        context = require_tenant_context(context)

        if context.tenant_id != rule_version.tenant_id:
            raise PermissionError("Risk rule tenant does not match context.")

        if not rule_version.is_approved_active():
            return

        active_rules = [
            rule
            for rule in self.risk_repository.get_rule_lineage(
                context,
                rule_version.risk_definition_id
            )
            if rule.is_approved_active()
            and rule.rule_version_id != rule_version.rule_version_id
        ]

        for existing in active_rules:
            if rule_version.overlaps_effective_period(existing):
                raise RiskRuleConflictError(
                    "Approved active risk rule period overlaps existing rule."
                )


def _validate_period(
    period_start: datetime,
    period_end: datetime
) -> None:
    if period_start > period_end:
        raise ValueError("period_start must be before or equal to period_end.")
