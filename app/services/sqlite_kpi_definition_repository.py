import json
from datetime import datetime
from typing import Any

from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi import (
    FormulaStatus,
    FormulaVersion,
    KPIDefinition,
    KPIDomain,
    KPILifecycle,
    KPIThreshold,
)


class SQLiteKPIDefinitionRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def upsert_definition(
        self,
        context: TenantContext | None,
        definition: KPIDefinition
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, definition.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO kpi_definitions (
                    tenant_id,
                    kpi_id,
                    name,
                    description,
                    domain,
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
                definition.kpi_id,
                definition.name,
                definition.description,
                definition.domain.value,
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
        kpi_id: str
    ) -> KPIDefinition | None:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    kpi_id,
                    name,
                    description,
                    domain,
                    lifecycle,
                    owner_user_id,
                    steward_user_id,
                    created_by,
                    created_at,
                    updated_at,
                    metadata_json
                FROM kpi_definitions
                WHERE tenant_id = ?
                  AND kpi_id = ?
            """, (
                context.tenant_id,
                kpi_id,
            ))

            row = cursor.fetchone()

        if row is None:
            return None

        definition = self._definition_from_row(row)
        definition.thresholds = self.list_thresholds(context, kpi_id)
        definition.formula_versions = self.list_formula_versions(context, kpi_id)

        return definition

    def list_definitions(
        self,
        context: TenantContext | None
    ) -> list[KPIDefinition]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    kpi_id,
                    name,
                    description,
                    domain,
                    lifecycle,
                    owner_user_id,
                    steward_user_id,
                    created_by,
                    created_at,
                    updated_at,
                    metadata_json
                FROM kpi_definitions
                WHERE tenant_id = ?
                ORDER BY name
            """, (
                context.tenant_id,
            ))
            rows = cursor.fetchall()

        definitions = []

        for row in rows:
            definition = self._definition_from_row(row)
            definition.thresholds = self.list_thresholds(
                context,
                definition.kpi_id
            )
            definition.formula_versions = self.list_formula_versions(
                context,
                definition.kpi_id
            )
            definitions.append(definition)

        return definitions

    def update_lifecycle(
        self,
        context: TenantContext | None,
        kpi_id: str,
        lifecycle: KPILifecycle | str
    ) -> KPIDefinition:
        context = require_tenant_context(context)
        lifecycle = KPILifecycle.from_value(lifecycle)
        definition = self.get_definition(context, kpi_id)

        if definition is None:
            raise ValueError(f"KPI definition not found: {kpi_id}")

        definition.move_to_lifecycle(lifecycle)
        self.upsert_definition(context, definition)

        return definition

    def upsert_threshold(
        self,
        context: TenantContext | None,
        threshold: KPIThreshold
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, threshold.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO kpi_thresholds (
                    tenant_id,
                    threshold_id,
                    kpi_id,
                    name,
                    risk_level,
                    target,
                    minimum,
                    maximum,
                    created_by,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                threshold.tenant_id,
                threshold.threshold_id,
                threshold.kpi_id,
                threshold.name,
                threshold.risk_level,
                threshold.target,
                threshold.minimum,
                threshold.maximum,
                threshold.created_by,
                _dt_to_text(threshold.created_at),
            ))
            conn.commit()

    def list_thresholds(
        self,
        context: TenantContext | None,
        kpi_id: str
    ) -> list[KPIThreshold]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    threshold_id,
                    tenant_id,
                    kpi_id,
                    name,
                    risk_level,
                    target,
                    minimum,
                    maximum,
                    created_by,
                    created_at
                FROM kpi_thresholds
                WHERE tenant_id = ?
                  AND kpi_id = ?
                ORDER BY name
            """, (
                context.tenant_id,
                kpi_id,
            ))
            rows = cursor.fetchall()

        return [
            self._threshold_from_row(row)
            for row in rows
        ]

    def upsert_formula_version(
        self,
        context: TenantContext | None,
        formula_version: FormulaVersion
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(context, formula_version.tenant_id)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO formula_versions (
                    tenant_id,
                    formula_version_id,
                    kpi_id,
                    version,
                    expression,
                    status,
                    created_by,
                    approved_by,
                    created_at,
                    approved_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                formula_version.tenant_id,
                formula_version.formula_version_id,
                formula_version.kpi_id,
                formula_version.version,
                formula_version.expression,
                formula_version.status.value,
                formula_version.created_by,
                formula_version.approved_by,
                _dt_to_text(formula_version.created_at),
                _dt_to_text(formula_version.approved_at),
                formula_version.notes,
            ))
            conn.commit()

    def get_formula_version(
        self,
        context: TenantContext | None,
        formula_version_id: str
    ) -> FormulaVersion | None:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    formula_version_id,
                    tenant_id,
                    kpi_id,
                    version,
                    expression,
                    created_by,
                    status,
                    approved_by,
                    created_at,
                    approved_at,
                    notes
                FROM formula_versions
                WHERE tenant_id = ?
                  AND formula_version_id = ?
            """, (
                context.tenant_id,
                formula_version_id,
            ))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._formula_from_row(row)

    def list_formula_versions(
        self,
        context: TenantContext | None,
        kpi_id: str
    ) -> list[FormulaVersion]:
        context = require_tenant_context(context)

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    formula_version_id,
                    tenant_id,
                    kpi_id,
                    version,
                    expression,
                    created_by,
                    status,
                    approved_by,
                    created_at,
                    approved_at,
                    notes
                FROM formula_versions
                WHERE tenant_id = ?
                  AND kpi_id = ?
                ORDER BY created_at
            """, (
                context.tenant_id,
                kpi_id,
            ))
            rows = cursor.fetchall()

        return [
            self._formula_from_row(row)
            for row in rows
        ]

    def _definition_from_row(self, row: tuple[Any, ...]) -> KPIDefinition:
        return KPIDefinition(
            tenant_id=row[0],
            kpi_id=row[1],
            name=row[2],
            description=row[3],
            domain=KPIDomain.from_value(row[4]),
            lifecycle=KPILifecycle.from_value(row[5]),
            owner_user_id=row[6],
            steward_user_id=row[7],
            created_by=row[8],
            created_at=_text_to_dt(row[9]),
            updated_at=_text_to_dt(row[10]),
            metadata=json.loads(row[11] or "{}"),
        )

    def _threshold_from_row(self, row: tuple[Any, ...]) -> KPIThreshold:
        return KPIThreshold(
            threshold_id=row[0],
            tenant_id=row[1],
            kpi_id=row[2],
            name=row[3],
            risk_level=row[4],
            target=row[5],
            minimum=row[6],
            maximum=row[7],
            created_by=row[8],
            created_at=_text_to_dt(row[9]),
        )

    def _formula_from_row(self, row: tuple[Any, ...]) -> FormulaVersion:
        return FormulaVersion(
            formula_version_id=row[0],
            tenant_id=row[1],
            kpi_id=row[2],
            version=row[3],
            expression=row[4],
            created_by=row[5],
            status=FormulaStatus.from_value(row[6]),
            approved_by=row[7],
            created_at=_text_to_dt(row[8]),
            approved_at=_text_to_dt(row[9]) if row[9] else None,
            notes=row[10] or "",
        )

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
