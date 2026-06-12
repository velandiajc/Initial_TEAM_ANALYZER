import json
from datetime import date, datetime
from typing import Protocol

from app.core.tenant_context import TenantContext, require_tenant_context
from app.domain.operational_impact import (
    ImpactDirection,
    ImpactGovernanceStatus,
    ImpactLevel,
    OperationalImpactAssessment,
    OperationalImpactDefinition,
    OperationalImpactFactor,
    OperationalImpactTimelineEvent,
    PriorityLevel,
    RiskPriorityAssessment,
)


def _context(context):
    return require_tenant_context(context)


def _same_tenant(context, tenant_id):
    if context.tenant_id != tenant_id:
        raise PermissionError("Repository access must be tenant-scoped.")


def _required(value, field_name):
    if not value:
        raise ValueError(f"{field_name} is required for persistence.")


class OperationalImpactDefinitionRepository(Protocol):
    def save(self, context, definition) -> None: ...
    def get_version(self, context, definition_id, version): ...
    def get_active(self, context, definition_id): ...
    def list_versions(self, context, definition_id): ...


class OperationalImpactFactorRepository(Protocol):
    def save(self, context, factor) -> None: ...
    def get_version(self, context, factor_id, version): ...
    def list_for_definition(self, context, definition_id, definition_version): ...
    def list_active_for_definition(
        self, context, definition_id, definition_version
    ): ...


class OperationalImpactAssessmentRepository(Protocol):
    def save(self, context, assessment) -> None: ...
    def get_by_id(self, context, assessment_id): ...
    def list_for_entity(self, context, entity_type, entity_id): ...


class RiskPriorityAssessmentRepository(Protocol):
    def save(self, context, assessment) -> None: ...
    def get_by_id(self, context, assessment_id): ...
    def list_for_entity(self, context, entity_type, entity_id): ...


class OperationalImpactTimelineRepository(Protocol):
    def save(self, context, event) -> None: ...
    def list_for_employee(self, context, employee_id): ...


class SQLiteOperationalImpactDefinitionRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, definition):
        context = _context(context)
        _same_tenant(context, definition.tenant_id)
        existing = self.get_version(
            context,
            definition.impact_definition_id,
            definition.impact_definition_version,
        )
        if existing:
            immutable = (
                "tenant_id",
                "impact_definition_id",
                "impact_definition_version",
                "name",
                "description",
                "impact_category",
                "owner",
                "steward",
                "effective_date",
                "created_by",
                "created_at",
            )
            if any(
                getattr(existing, name) != getattr(definition, name)
                for name in immutable
            ):
                raise PermissionError(
                    "Approved definition versions are immutable."
                )
        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO operational_impact_definitions (
                    tenant_id, impact_definition_id,
                    impact_definition_version, name, description,
                    impact_category, owner, steward, status, effective_date,
                    created_by, updated_by, created_at, updated_at,
                    approved_by, approved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    tenant_id,
                    impact_definition_id,
                    impact_definition_version
                ) DO UPDATE SET
                    status = excluded.status,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at,
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at
            """, (
                definition.tenant_id,
                definition.impact_definition_id,
                definition.impact_definition_version,
                definition.name,
                definition.description,
                definition.impact_category,
                definition.owner,
                definition.steward,
                definition.status.value,
                definition.effective_date.isoformat(),
                definition.created_by,
                definition.updated_by,
                definition.created_at.isoformat(),
                definition.updated_at.isoformat(),
                definition.approved_by,
                (
                    definition.approved_at.isoformat()
                    if definition.approved_at
                    else None
                ),
            ))

    def get_version(self, context, definition_id, version):
        context = _context(context)
        with self.database_service.connect() as conn:
            row = conn.execute("""
                SELECT tenant_id, impact_definition_id, name, description,
                       impact_category, owner, steward, status,
                       impact_definition_version, effective_date, created_by,
                       updated_by, created_at, updated_at, approved_by,
                       approved_at
                FROM operational_impact_definitions
                WHERE tenant_id = ?
                  AND impact_definition_id = ?
                  AND impact_definition_version = ?
            """, (context.tenant_id, definition_id, version)).fetchone()
        return self._from_row(row) if row else None

    def get_active(self, context, definition_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute("""
                SELECT tenant_id, impact_definition_id, name, description,
                       impact_category, owner, steward, status,
                       impact_definition_version, effective_date, created_by,
                       updated_by, created_at, updated_at, approved_by,
                       approved_at
                FROM operational_impact_definitions
                WHERE tenant_id = ?
                  AND impact_definition_id = ?
                  AND status = 'ACTIVE'
                ORDER BY effective_date DESC, created_at DESC
            """, (context.tenant_id, definition_id)).fetchall()
        if len(rows) > 1:
            raise ValueError("Multiple active impact definition versions.")
        return self._from_row(rows[0]) if rows else None

    def list_versions(self, context, definition_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute("""
                SELECT tenant_id, impact_definition_id, name, description,
                       impact_category, owner, steward, status,
                       impact_definition_version, effective_date, created_by,
                       updated_by, created_at, updated_at, approved_by,
                       approved_at
                FROM operational_impact_definitions
                WHERE tenant_id = ? AND impact_definition_id = ?
                ORDER BY effective_date, created_at
            """, (context.tenant_id, definition_id)).fetchall()
        return [self._from_row(row) for row in rows]

    def deactivate_other_versions(self, context, definition):
        context = _context(context)
        with self.database_service.connect() as conn:
            conn.execute("""
                UPDATE operational_impact_definitions
                SET status = 'DEPRECATED',
                    updated_by = ?,
                    updated_at = ?
                WHERE tenant_id = ?
                  AND impact_definition_id = ?
                  AND impact_definition_version <> ?
                  AND status = 'ACTIVE'
            """, (
                context.user_id,
                datetime.now().astimezone().isoformat(),
                context.tenant_id,
                definition.impact_definition_id,
                definition.impact_definition_version,
            ))

    def _from_row(self, row):
        return OperationalImpactDefinition(
            tenant_id=row[0],
            impact_definition_id=row[1],
            name=row[2],
            description=row[3],
            impact_category=row[4],
            owner=row[5],
            steward=row[6],
            status=ImpactGovernanceStatus.from_value(row[7]),
            impact_definition_version=row[8],
            effective_date=date.fromisoformat(row[9]),
            created_by=row[10],
            updated_by=row[11],
            created_at=datetime.fromisoformat(row[12]),
            updated_at=datetime.fromisoformat(row[13]),
            approved_by=row[14],
            approved_at=(
                datetime.fromisoformat(row[15])
                if row[15]
                else None
            ),
        )


class SQLiteOperationalImpactFactorRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, factor):
        context = _context(context)
        _same_tenant(context, factor.tenant_id)
        existing = self.get_version(
            context,
            factor.impact_factor_id,
            factor.impact_factor_version,
        )
        if existing:
            immutable = (
                "tenant_id",
                "impact_factor_id",
                "impact_factor_version",
                "impact_definition_id",
                "impact_definition_version",
                "name",
                "description",
                "source_reference",
                "weight",
                "direction",
                "threshold_version",
                "threshold_min",
                "threshold_max",
                "owner",
                "steward",
                "effective_date",
                "created_by",
                "created_at",
            )
            if any(
                getattr(existing, name) != getattr(factor, name)
                for name in immutable
            ):
                raise PermissionError(
                    "Approved factor versions are immutable."
                )
        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO operational_impact_factors (
                    tenant_id, impact_factor_id, impact_factor_version,
                    impact_definition_id, impact_definition_version, name,
                    description, source_reference, weight, direction,
                    threshold_version, threshold_min, threshold_max, owner,
                    steward, status, effective_date, created_by, updated_by,
                    created_at, updated_at, approved_by, approved_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT (
                    tenant_id,
                    impact_factor_id,
                    impact_factor_version
                ) DO UPDATE SET
                    status = excluded.status,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at,
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at
            """, (
                factor.tenant_id,
                factor.impact_factor_id,
                factor.impact_factor_version,
                factor.impact_definition_id,
                factor.impact_definition_version,
                factor.name,
                factor.description,
                factor.source_reference,
                factor.weight,
                factor.direction.value,
                factor.threshold_version,
                factor.threshold_min,
                factor.threshold_max,
                factor.owner,
                factor.steward,
                factor.status.value,
                factor.effective_date.isoformat(),
                factor.created_by,
                factor.updated_by,
                factor.created_at.isoformat(),
                factor.updated_at.isoformat(),
                factor.approved_by,
                (
                    factor.approved_at.isoformat()
                    if factor.approved_at
                    else None
                ),
            ))

    def get_version(self, context, factor_id, version):
        context = _context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select()
                + """
                WHERE tenant_id = ?
                  AND impact_factor_id = ?
                  AND impact_factor_version = ?
                """,
                (context.tenant_id, factor_id, version),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_definition(self, context, definition_id, definition_version):
        context = _context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select()
                + """
                WHERE tenant_id = ?
                  AND impact_definition_id = ?
                  AND impact_definition_version = ?
                ORDER BY name, impact_factor_id
                """,
                (context.tenant_id, definition_id, definition_version),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_active_for_definition(
        self,
        context,
        definition_id,
        definition_version,
    ):
        return [
            factor
            for factor in self.list_for_definition(
                context,
                definition_id,
                definition_version,
            )
            if factor.status == ImpactGovernanceStatus.ACTIVE
        ]

    def deactivate_other_versions(self, context, factor):
        context = _context(context)
        with self.database_service.connect() as conn:
            conn.execute("""
                UPDATE operational_impact_factors
                SET status = 'DEPRECATED',
                    updated_by = ?,
                    updated_at = ?
                WHERE tenant_id = ?
                  AND impact_factor_id = ?
                  AND impact_factor_version <> ?
                  AND status = 'ACTIVE'
            """, (
                context.user_id,
                datetime.now().astimezone().isoformat(),
                context.tenant_id,
                factor.impact_factor_id,
                factor.impact_factor_version,
            ))

    def _select(self):
        return """
            SELECT tenant_id, impact_factor_id, impact_definition_id,
                   impact_definition_version, name, description,
                   source_reference, weight, direction, threshold_version,
                   threshold_min, threshold_max, impact_factor_version,
                   owner, steward, status, effective_date, created_by,
                   updated_by, created_at, updated_at, approved_by, approved_at
            FROM operational_impact_factors
        """

    def _from_row(self, row):
        return OperationalImpactFactor(
            tenant_id=row[0],
            impact_factor_id=row[1],
            impact_definition_id=row[2],
            impact_definition_version=row[3],
            name=row[4],
            description=row[5],
            source_reference=row[6],
            weight=row[7],
            direction=ImpactDirection.from_value(row[8]),
            threshold_version=row[9],
            threshold_min=row[10],
            threshold_max=row[11],
            impact_factor_version=row[12],
            owner=row[13],
            steward=row[14],
            status=ImpactGovernanceStatus.from_value(row[15]),
            effective_date=date.fromisoformat(row[16]),
            created_by=row[17],
            updated_by=row[18],
            created_at=datetime.fromisoformat(row[19]),
            updated_at=datetime.fromisoformat(row[20]),
            approved_by=row[21],
            approved_at=(
                datetime.fromisoformat(row[22])
                if row[22]
                else None
            ),
        )


class SQLiteOperationalImpactAssessmentRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, assessment):
        context = _context(context)
        _same_tenant(context, assessment.tenant_id)
        for value, name in (
            (assessment.lineage_id, "lineage_id"),
            (assessment.impact_definition_version, "impact_definition_version"),
            (assessment.impact_factor_ids, "impact_factor_ids"),
            (assessment.impact_factor_versions, "impact_factor_versions"),
            (assessment.threshold_versions, "threshold_versions"),
        ):
            _required(value, name)
        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO operational_impact_assessments (
                    tenant_id, impact_assessment_id, impact_definition_id,
                    entity_type, entity_id, assessment_period_start,
                    assessment_period_end, impact_score, impact_level,
                    impact_definition_version, impact_factor_ids_json,
                    impact_factor_versions_json, threshold_versions_json,
                    weight_snapshots_json, factor_score_snapshots_json,
                    source_kpi_result_ids_json,
                    source_risk_result_ids_json, lineage_id, created_by,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                assessment.tenant_id,
                assessment.impact_assessment_id,
                assessment.impact_definition_id,
                assessment.entity_type,
                assessment.entity_id,
                assessment.assessment_period_start.isoformat(),
                assessment.assessment_period_end.isoformat(),
                assessment.impact_score,
                assessment.impact_level.value,
                assessment.impact_definition_version,
                json.dumps(assessment.impact_factor_ids),
                json.dumps(dict(assessment.impact_factor_versions)),
                json.dumps(dict(assessment.threshold_versions)),
                json.dumps(dict(assessment.weight_snapshots)),
                json.dumps(dict(assessment.factor_score_snapshots)),
                json.dumps(assessment.source_kpi_result_ids),
                json.dumps(assessment.source_risk_result_ids),
                assessment.lineage_id,
                assessment.created_by,
                assessment.created_at.isoformat(),
            ))

    def get_by_id(self, context, assessment_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select()
                + " WHERE tenant_id = ? AND impact_assessment_id = ?",
                (context.tenant_id, assessment_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_entity(self, context, entity_type, entity_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select()
                + """
                WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
                ORDER BY created_at, impact_assessment_id
                """,
                (context.tenant_id, entity_type, entity_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _select(self):
        return """
            SELECT tenant_id, impact_assessment_id, impact_definition_id,
                   entity_type, entity_id, assessment_period_start,
                   assessment_period_end, impact_score, impact_level,
                   impact_definition_version, impact_factor_ids_json,
                   impact_factor_versions_json, threshold_versions_json,
                   weight_snapshots_json, factor_score_snapshots_json,
                   source_kpi_result_ids_json, source_risk_result_ids_json,
                   lineage_id, created_by, created_at
            FROM operational_impact_assessments
        """

    def _from_row(self, row):
        return OperationalImpactAssessment(
            tenant_id=row[0],
            impact_assessment_id=row[1],
            impact_definition_id=row[2],
            entity_type=row[3],
            entity_id=row[4],
            assessment_period_start=datetime.fromisoformat(row[5]),
            assessment_period_end=datetime.fromisoformat(row[6]),
            impact_score=row[7],
            impact_level=ImpactLevel.from_value(row[8]),
            impact_definition_version=row[9],
            impact_factor_ids=tuple(json.loads(row[10])),
            impact_factor_versions=json.loads(row[11]),
            threshold_versions=json.loads(row[12]),
            weight_snapshots=json.loads(row[13]),
            factor_score_snapshots=json.loads(row[14]),
            source_kpi_result_ids=tuple(json.loads(row[15])),
            source_risk_result_ids=tuple(json.loads(row[16])),
            lineage_id=row[17],
            created_by=row[18],
            created_at=datetime.fromisoformat(row[19]),
        )


class SQLiteRiskPriorityAssessmentRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, assessment):
        context = _context(context)
        _same_tenant(context, assessment.tenant_id)
        for value, name in (
            (assessment.lineage_id, "lineage_id"),
            (assessment.risk_result_id, "risk_result_id"),
            (assessment.risk_definition_version, "risk_definition_version"),
            (assessment.risk_rule_version, "risk_rule_version"),
            (assessment.impact_assessment_id, "impact_assessment_id"),
            (
                assessment.impact_definition_version,
                "impact_definition_version",
            ),
        ):
            _required(value, name)
        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO risk_priority_assessments (
                    tenant_id, priority_assessment_id, risk_result_id,
                    risk_definition_version, risk_rule_version,
                    impact_assessment_id, impact_definition_version,
                    entity_type, entity_id, risk_score_snapshot,
                    impact_score_snapshot, priority_score, priority_level,
                    priority_reason, lineage_id, created_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assessment.tenant_id,
                assessment.priority_assessment_id,
                assessment.risk_result_id,
                assessment.risk_definition_version,
                assessment.risk_rule_version,
                assessment.impact_assessment_id,
                assessment.impact_definition_version,
                assessment.entity_type,
                assessment.entity_id,
                assessment.risk_score_snapshot,
                assessment.impact_score_snapshot,
                assessment.priority_score,
                assessment.priority_level.value,
                assessment.priority_reason,
                assessment.lineage_id,
                assessment.created_by,
                assessment.created_at.isoformat(),
            ))

    def get_by_id(self, context, assessment_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            row = conn.execute(
                self._select()
                + " WHERE tenant_id = ? AND priority_assessment_id = ?",
                (context.tenant_id, assessment_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_entity(self, context, entity_type, entity_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute(
                self._select()
                + """
                WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
                ORDER BY created_at, priority_assessment_id
                """,
                (context.tenant_id, entity_type, entity_id),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def _select(self):
        return """
            SELECT tenant_id, priority_assessment_id, risk_result_id,
                   risk_definition_version, risk_rule_version,
                   impact_assessment_id, impact_definition_version,
                   entity_type, entity_id, risk_score_snapshot,
                   impact_score_snapshot, priority_score, priority_level,
                   priority_reason, lineage_id, created_by, created_at
            FROM risk_priority_assessments
        """

    def _from_row(self, row):
        return RiskPriorityAssessment(
            tenant_id=row[0],
            priority_assessment_id=row[1],
            risk_result_id=row[2],
            risk_definition_version=row[3],
            risk_rule_version=row[4],
            impact_assessment_id=row[5],
            impact_definition_version=row[6],
            entity_type=row[7],
            entity_id=row[8],
            risk_score_snapshot=row[9],
            impact_score_snapshot=row[10],
            priority_score=row[11],
            priority_level=PriorityLevel.from_value(row[12]),
            priority_reason=row[13],
            lineage_id=row[14],
            created_by=row[15],
            created_at=datetime.fromisoformat(row[16]),
        )


class SQLiteOperationalImpactTimelineRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def save(self, context, event):
        context = _context(context)
        _same_tenant(context, event.tenant_id)
        with self.database_service.connect() as conn:
            conn.execute("""
                INSERT INTO operational_impact_timeline_events (
                    tenant_id, timeline_event_id, employee_id,
                    impact_assessment_id, priority_assessment_id, event_type,
                    material_change_reason, impact_level_snapshot,
                    priority_level_snapshot, created_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.tenant_id,
                event.timeline_event_id,
                event.employee_id,
                event.impact_assessment_id,
                event.priority_assessment_id,
                event.event_type,
                event.material_change_reason,
                event.impact_level_snapshot.value,
                event.priority_level_snapshot.value,
                event.created_by,
                event.created_at.isoformat(),
            ))

    def list_for_employee(self, context, employee_id):
        context = _context(context)
        with self.database_service.connect() as conn:
            rows = conn.execute("""
                SELECT tenant_id, timeline_event_id, employee_id,
                       impact_assessment_id, priority_assessment_id,
                       event_type, material_change_reason,
                       impact_level_snapshot, priority_level_snapshot,
                       created_by, created_at
                FROM operational_impact_timeline_events
                WHERE tenant_id = ? AND employee_id = ?
                ORDER BY created_at, timeline_event_id
            """, (context.tenant_id, employee_id)).fetchall()
        return [
            OperationalImpactTimelineEvent(
                tenant_id=row[0],
                timeline_event_id=row[1],
                employee_id=row[2],
                impact_assessment_id=row[3],
                priority_assessment_id=row[4],
                event_type=row[5],
                material_change_reason=row[6],
                impact_level_snapshot=ImpactLevel.from_value(row[7]),
                priority_level_snapshot=PriorityLevel.from_value(row[8]),
                created_by=row[9],
                created_at=datetime.fromisoformat(row[10]),
            )
            for row in rows
        ]
