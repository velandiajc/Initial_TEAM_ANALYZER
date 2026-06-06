import json
from datetime import datetime
from typing import Any

from app.core.permissions import KPIPermission, RBACService
from app.core.tenant_context import TenantContext, require_tenant_context
from app.models.kpi_calculation import (
    KPICalculationResult,
    KPICalculationStatus,
)


class SQLiteKPICalculationResultRepository:
    def __init__(
        self,
        database_service,
        rbac_service: RBACService | None = None
    ):
        self.database_service = database_service
        self.rbac_service = rbac_service or RBACService()

    def save(
        self,
        context: TenantContext | None,
        result: KPICalculationResult
    ) -> None:
        context = require_tenant_context(context)
        self._require_same_tenant(
            context,
            result.tenant_id
        )

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO kpi_calculation_results (
                    tenant_id,
                    result_id,
                    kpi_id,
                    formula_version_id,
                    formula_version_number,
                    period_start,
                    period_end,
                    scope_json,
                    value,
                    status,
                    data_quality_status,
                    source_reference,
                    calculation_run_id,
                    calculated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.tenant_id,
                result.result_id,
                result.kpi_id,
                result.formula_version_id,
                result.formula_version_number,
                result.period_start.isoformat(),
                result.period_end.isoformat(),
                json.dumps(result.scope),
                result.value,
                result.status.value,
                result.data_quality_status,
                result.source_reference,
                result.calculation_run_id,
                result.calculated_at.isoformat(),
                json.dumps(result.metadata),
            ))
            conn.commit()

    def get_result(
        self,
        context: TenantContext | None,
        result_id: str
    ) -> KPICalculationResult | None:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.VIEW_KPI_RESULTS
        )

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    result_id,
                    kpi_id,
                    formula_version_id,
                    formula_version_number,
                    period_start,
                    period_end,
                    scope_json,
                    value,
                    status,
                    data_quality_status,
                    source_reference,
                    calculation_run_id,
                    calculated_at,
                    metadata_json
                FROM kpi_calculation_results
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

    def list_results_for_kpi(
        self,
        context: TenantContext | None,
        kpi_id: str
    ) -> list[KPICalculationResult]:
        context = require_tenant_context(context)
        self.rbac_service.require_permission(
            context,
            KPIPermission.VIEW_KPI_RESULTS
        )

        with self.database_service.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    tenant_id,
                    result_id,
                    kpi_id,
                    formula_version_id,
                    formula_version_number,
                    period_start,
                    period_end,
                    scope_json,
                    value,
                    status,
                    data_quality_status,
                    source_reference,
                    calculation_run_id,
                    calculated_at,
                    metadata_json
                FROM kpi_calculation_results
                WHERE tenant_id = ?
                  AND kpi_id = ?
                ORDER BY calculated_at
            """, (
                context.tenant_id,
                kpi_id,
            ))
            rows = cursor.fetchall()

        return [
            self._result_from_row(row)
            for row in rows
        ]

    def _result_from_row(self, row: tuple[Any, ...]) -> KPICalculationResult:
        return KPICalculationResult(
            tenant_id=row[0],
            result_id=row[1],
            kpi_id=row[2],
            formula_version_id=row[3],
            formula_version_number=row[4],
            period_start=datetime.fromisoformat(row[5]),
            period_end=datetime.fromisoformat(row[6]),
            scope=json.loads(row[7] or "{}"),
            value=row[8],
            status=KPICalculationStatus.from_value(row[9]),
            data_quality_status=row[10],
            source_reference=row[11] or "",
            calculation_run_id=row[12],
            calculated_at=datetime.fromisoformat(row[13]),
            metadata=json.loads(row[14] or "{}"),
        )

    def _require_same_tenant(
        self,
        context: TenantContext,
        tenant_id: str
    ) -> None:
        if context.tenant_id != tenant_id:
            raise PermissionError("Repository access must be tenant-scoped.")
