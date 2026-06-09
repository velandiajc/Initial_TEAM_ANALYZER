import json
from datetime import datetime
from typing import Any

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.risk import (
    RiskAssessmentResult,
    RiskAssessmentStatus,
    RiskDefinition,
    RiskDefinitionLifecycle,
    RiskLevel,
    RiskRuleStatus,
    RiskRuleVersion,
)


class SQLiteRiskDefinitionRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def upsert_definition(
        self,
        context: TenantContext | None,
        definition: RiskDefinition
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, definition.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO risk_definitions (
                    tenant_id,
                    risk_definition_id,
                    name,
                    description,
                    category,
                    lifecycle,
                    owner_user_id,
                    steward_user_id,
                    created_by,
                    created_at,
                    updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                definition.tenant_id,
                definition.risk_definition_id,
                definition.name,
                definition.description,
                definition.category,
                definition.lifecycle.value,
                definition.owner_user_id,
                definition.steward_user_id,
                definition.created_by,
                _dt_to_text(definition.created_at),
                _dt_to_text(definition.updated_at),
                json.dumps(definition.metadata),
            ))
            conn.commit()

    def get_definition(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> RiskDefinition | None:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    risk_definition_id,
                    name,
                    description,
                    category,
                    lifecycle,
                    owner_user_id,
                    steward_user_id,
                    created_by,
                    created_at,
                    updated_at,
                    metadata_json
                FROM risk_definitions
                WHERE tenant_id = ?
                  AND risk_definition_id = ?
            """, (
                context.tenant_id,
                risk_definition_id,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        definition = self._definition_from_row(row)
        definition.rule_versions = self.list_rule_versions(
            context,
            risk_definition_id
        )

        return definition

    def list_definitions(
        self,
        context: TenantContext | None
    ) -> list[RiskDefinition]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    risk_definition_id,
                    name,
                    description,
                    category,
                    lifecycle,
                    owner_user_id,
                    steward_user_id,
                    created_by,
                    created_at,
                    updated_at,
                    metadata_json
                FROM risk_definitions
                WHERE tenant_id = ?
                ORDER BY name
            """, (
                context.tenant_id,
            ))
            rows = cursor.fetchall()

        definitions = []

        for row in rows:
            definition = self._definition_from_row(row)
            definition.rule_versions = self.list_rule_versions(
                context,
                definition.risk_definition_id
            )
            definitions.append(definition)

        return definitions

    def update_lifecycle(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        lifecycle: RiskDefinitionLifecycle | str
    ) -> RiskDefinition:
        context = require_tenant_context(context)
        lifecycle = RiskDefinitionLifecycle.from_value(lifecycle)
        definition = self.get_definition(context, risk_definition_id)

        if definition is None:
            raise ValueError(
                f"Risk definition not found: {risk_definition_id}"
            )

        definition.move_to_lifecycle(lifecycle)
        self.upsert_definition(context, definition)

        return definition

    def upsert_rule_version(
        self,
        context: TenantContext | None,
        rule_version: RiskRuleVersion
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, rule_version.tenant_id)
        self._reject_approved_rule_mutation(context, rule_version)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO risk_rule_versions (
                    tenant_id,
                    rule_version_id,
                    risk_definition_id,
                    version,
                    handler_key,
                    parameters_json,
                    status,
                    created_by,
                    approved_by,
                    created_at,
                    approved_at,
                    effective_from,
                    effective_to,
                    supersedes_rule_version_id,
                    is_active,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_version.tenant_id,
                rule_version.rule_version_id,
                rule_version.risk_definition_id,
                rule_version.version,
                rule_version.handler_key,
                json.dumps(rule_version.parameters),
                rule_version.status.value,
                rule_version.created_by,
                rule_version.approved_by,
                _dt_to_text(rule_version.created_at),
                _dt_to_text(rule_version.approved_at),
                _dt_to_text(rule_version.effective_from),
                _dt_to_text(rule_version.effective_to),
                rule_version.supersedes_rule_version_id,
                1 if rule_version.is_active else 0,
                rule_version.notes,
            ))
            conn.commit()

    def get_rule_version(
        self,
        context: TenantContext | None,
        rule_version_id: str
    ) -> RiskRuleVersion | None:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    rule_version_id,
                    tenant_id,
                    risk_definition_id,
                    version,
                    handler_key,
                    parameters_json,
                    created_by,
                    status,
                    approved_by,
                    created_at,
                    approved_at,
                    effective_from,
                    effective_to,
                    supersedes_rule_version_id,
                    is_active,
                    notes
                FROM risk_rule_versions
                WHERE tenant_id = ?
                  AND rule_version_id = ?
            """, (
                context.tenant_id,
                rule_version_id,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._rule_version_from_row(row)

    def list_rule_versions(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> list[RiskRuleVersion]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    rule_version_id,
                    tenant_id,
                    risk_definition_id,
                    version,
                    handler_key,
                    parameters_json,
                    created_by,
                    status,
                    approved_by,
                    created_at,
                    approved_at,
                    effective_from,
                    effective_to,
                    supersedes_rule_version_id,
                    is_active,
                    notes
                FROM risk_rule_versions
                WHERE tenant_id = ?
                  AND risk_definition_id = ?
                ORDER BY created_at
            """, (
                context.tenant_id,
                risk_definition_id,
            ))
            rows = cursor.fetchall()

        return [
            self._rule_version_from_row(row)
            for row in rows
        ]

    def get_approved_active_rules_for_period(
        self,
        context: TenantContext | None,
        risk_definition_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> list[RiskRuleVersion]:
        rules = [
            rule
            for rule in self.list_rule_versions(context, risk_definition_id)
            if rule.is_approved_active()
        ]

        return [
            rule
            for rule in rules
            if rule.covers_period(period_start, period_end)
        ]

    def get_rule_lineage(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> list[RiskRuleVersion]:
        return self.list_rule_versions(context, risk_definition_id)

    def save_result(
        self,
        context: TenantContext | None,
        result: RiskAssessmentResult
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, result.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO risk_assessment_results (
                    tenant_id,
                    result_id,
                    risk_definition_id,
                    rule_version_id,
                    rule_version_number,
                    entity_type,
                    entity_id,
                    period_start,
                    period_end,
                    risk_level,
                    status,
                    reason,
                    evidence_json,
                    source_reference,
                    assessment_run_id,
                    assessed_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.tenant_id,
                result.result_id,
                result.risk_definition_id,
                result.rule_version_id,
                result.rule_version_number,
                result.entity_type,
                result.entity_id,
                _dt_to_text(result.period_start),
                _dt_to_text(result.period_end),
                result.risk_level.value,
                result.status.value,
                result.reason,
                json.dumps(result.evidence),
                result.source_reference,
                result.assessment_run_id,
                _dt_to_text(result.assessed_at),
                json.dumps(result.metadata),
            ))
            conn.commit()

    def get_result(
        self,
        context: TenantContext | None,
        result_id: str
    ) -> RiskAssessmentResult | None:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    result_id,
                    risk_definition_id,
                    rule_version_id,
                    rule_version_number,
                    entity_type,
                    entity_id,
                    period_start,
                    period_end,
                    risk_level,
                    status,
                    reason,
                    evidence_json,
                    source_reference,
                    assessment_run_id,
                    assessed_at,
                    metadata_json
                FROM risk_assessment_results
                WHERE tenant_id = ?
                  AND result_id = ?
            """, (
                context.tenant_id,
                result_id,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._result_from_row(row)

    def list_results_for_definition(
        self,
        context: TenantContext | None,
        risk_definition_id: str
    ) -> list[RiskAssessmentResult]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    result_id,
                    risk_definition_id,
                    rule_version_id,
                    rule_version_number,
                    entity_type,
                    entity_id,
                    period_start,
                    period_end,
                    risk_level,
                    status,
                    reason,
                    evidence_json,
                    source_reference,
                    assessment_run_id,
                    assessed_at,
                    metadata_json
                FROM risk_assessment_results
                WHERE tenant_id = ?
                  AND risk_definition_id = ?
                ORDER BY assessed_at
            """, (
                context.tenant_id,
                risk_definition_id,
            ))
            rows = cursor.fetchall()

        return [
            self._result_from_row(row)
            for row in rows
        ]

    def _definition_from_row(self, row: tuple[Any, ...]) -> RiskDefinition:
        return RiskDefinition(
            tenant_id=row[0],
            risk_definition_id=row[1],
            name=row[2],
            description=row[3] or "",
            category=row[4],
            lifecycle=RiskDefinitionLifecycle.from_value(row[5]),
            owner_user_id=row[6],
            steward_user_id=row[7],
            created_by=row[8],
            created_at=_text_to_dt(row[9]),
            updated_at=_text_to_dt(row[10]),
            metadata=json.loads(row[11] or "{}"),
        )

    def _rule_version_from_row(self, row: tuple[Any, ...]) -> RiskRuleVersion:
        return RiskRuleVersion(
            rule_version_id=row[0],
            tenant_id=row[1],
            risk_definition_id=row[2],
            version=row[3],
            handler_key=row[4],
            parameters=json.loads(row[5] or "{}"),
            created_by=row[6],
            status=RiskRuleStatus.from_value(row[7]),
            approved_by=row[8],
            created_at=_text_to_dt(row[9]),
            approved_at=_text_to_dt(row[10]) if row[10] else None,
            effective_from=_text_to_dt(row[11]) if row[11] else None,
            effective_to=_text_to_dt(row[12]) if row[12] else None,
            supersedes_rule_version_id=row[13],
            is_active=bool(row[14]),
            notes=row[15] or "",
        )

    def _result_from_row(self, row: tuple[Any, ...]) -> RiskAssessmentResult:
        return RiskAssessmentResult(
            tenant_id=row[0],
            result_id=row[1],
            risk_definition_id=row[2],
            rule_version_id=row[3],
            rule_version_number=row[4],
            entity_type=row[5],
            entity_id=row[6],
            period_start=_text_to_dt(row[7]),
            period_end=_text_to_dt(row[8]),
            risk_level=RiskLevel.from_value(row[9]),
            status=RiskAssessmentStatus.from_value(row[10]),
            reason=row[11],
            evidence=json.loads(row[12] or "{}"),
            source_reference=row[13] or "",
            assessment_run_id=row[14],
            assessed_at=_text_to_dt(row[15]),
            metadata=json.loads(row[16] or "{}"),
        )

    def _reject_approved_rule_mutation(
        self,
        context: TenantContext,
        rule_version: RiskRuleVersion
    ) -> None:
        existing = self.get_rule_version(context, rule_version.rule_version_id)

        if existing is None or not existing.is_approved():
            return

        protected_fields = [
            "tenant_id",
            "risk_definition_id",
            "version",
            "handler_key",
            "parameters",
            "created_by",
            "effective_from",
            "effective_to",
            "supersedes_rule_version_id",
        ]

        for field_name in protected_fields:
            if getattr(existing, field_name) != getattr(rule_version, field_name):
                raise PermissionError("Approved risk rules are immutable.")

        if rule_version.status != RiskRuleStatus.APPROVED:
            raise PermissionError("Approved risk rules are immutable.")

    def _require_same_tenant(
        self,
        context: TenantContext,
        tenant_id: str
    ) -> None:
        if context.tenant_id != tenant_id:
            raise PermissionError("Repository access must be tenant-scoped.")


def _dt_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _text_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)
