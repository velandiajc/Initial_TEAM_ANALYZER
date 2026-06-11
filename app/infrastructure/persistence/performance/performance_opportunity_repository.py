from typing import Protocol

from app.core.tenant_context import TenantContext
from app.domain.performance.entities import PerformanceOpportunity
from app.domain.performance.value_objects import PerformanceOpportunityStatus
from app.infrastructure.persistence.performance._sqlite import (
    datetime_text,
    require_persistence_lineage,
    require_same_tenant,
    scoped_context,
    text_datetime,
)


class PerformanceOpportunityRepository(Protocol):
    def save(
        self,
        context: TenantContext | None,
        opportunity: PerformanceOpportunity,
    ) -> None: ...

    def get_by_id(
        self,
        context: TenantContext | None,
        opportunity_id: str,
    ) -> PerformanceOpportunity | None: ...

    def list_for_employee(
        self,
        context: TenantContext | None,
        employee_id: str,
    ) -> list[PerformanceOpportunity]: ...


class SQLitePerformanceOpportunityRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, opportunity) -> None:
        context = scoped_context(context)
        require_same_tenant(context, opportunity.tenant_id)
        require_persistence_lineage(
            opportunity.lineage_id,
            opportunity.evidence_pack_id,
            opportunity.risk_result_id,
        )
        existing = self.get_by_id(context, opportunity.opportunity_id)
        if existing is not None:
            self._update(context, existing, opportunity)
            return

        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO performance_opportunities (
                    tenant_id, opportunity_id, employee_id, opportunity_type,
                    business_reason, evidence_pack_id, risk_result_id, owner,
                    lineage_id, status, created_by, updated_by, created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opportunity.tenant_id,
                opportunity.opportunity_id,
                opportunity.employee_id,
                opportunity.opportunity_type,
                opportunity.business_reason,
                opportunity.evidence_pack_id,
                opportunity.risk_result_id,
                opportunity.owner,
                opportunity.lineage_id,
                opportunity.status.value,
                opportunity.created_by,
                opportunity.updated_by,
                datetime_text(opportunity.created_at),
                datetime_text(opportunity.updated_at),
            ))

    def get_by_id(self, context, opportunity_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            row = conn.execute("""
                SELECT tenant_id, opportunity_id, employee_id,
                       opportunity_type, business_reason, evidence_pack_id,
                       risk_result_id, owner, lineage_id, created_by,
                       updated_by, status, created_at, updated_at
                FROM performance_opportunities
                WHERE tenant_id = ? AND opportunity_id = ?
            """, (context.tenant_id, opportunity_id)).fetchone()
        return self._from_row(row) if row else None

    def list_for_employee(self, context, employee_id):
        context = scoped_context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute("""
                SELECT tenant_id, opportunity_id, employee_id,
                       opportunity_type, business_reason, evidence_pack_id,
                       risk_result_id, owner, lineage_id, created_by,
                       updated_by, status, created_at, updated_at
                FROM performance_opportunities
                WHERE tenant_id = ? AND employee_id = ?
                ORDER BY created_at, opportunity_id
            """, (context.tenant_id, employee_id)).fetchall()
        return [self._from_row(row) for row in rows]

    def _update(self, context, existing, opportunity) -> None:
        immutable_fields = (
            "tenant_id",
            "opportunity_id",
            "employee_id",
            "opportunity_type",
            "business_reason",
            "evidence_pack_id",
            "risk_result_id",
            "lineage_id",
            "created_by",
            "created_at",
        )
        if any(
            getattr(existing, name) != getattr(opportunity, name)
            for name in immutable_fields
        ):
            raise PermissionError("Historical opportunity fields are immutable.")
        with self.database_service.connect() as conn:
            conn.execute("""
                UPDATE performance_opportunities
                SET owner = ?, status = ?, updated_by = ?, updated_at = ?
                WHERE tenant_id = ? AND opportunity_id = ?
            """, (
                opportunity.owner,
                opportunity.status.value,
                opportunity.updated_by,
                datetime_text(opportunity.updated_at),
                context.tenant_id,
                opportunity.opportunity_id,
            ))

    def _from_row(self, row):
        return PerformanceOpportunity(
            tenant_id=row[0],
            opportunity_id=row[1],
            employee_id=row[2],
            opportunity_type=row[3],
            business_reason=row[4],
            evidence_pack_id=row[5],
            risk_result_id=row[6],
            owner=row[7],
            lineage_id=row[8],
            created_by=row[9],
            updated_by=row[10],
            status=PerformanceOpportunityStatus.from_value(row[11]),
            created_at=text_datetime(row[12]),
            updated_at=text_datetime(row[13]),
        )
