import sqlite3
from pathlib import Path

from app.services.pci_redaction_service import PCIRedactionService


class DatabaseService:
    def __init__(
        self,
        db_path="Data/database/team_analyzer.db",
        legacy_tenant_id="legacy-local",
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.legacy_tenant_id = str(legacy_tenant_id).strip()
        if not self.legacy_tenant_id:
            raise ValueError("legacy_tenant_id is required.")

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        pci_service = PCIRedactionService()
        connection.create_function(
            "pci_persistence_safe",
            1,
            lambda value: int(pci_service.is_persistence_safe(value)),
        )
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        with self.connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            cursor = conn.cursor()
            self._initialize_legacy_tables(cursor)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_definitions (
                    tenant_id TEXT NOT NULL,
                    kpi_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    domain TEXT NOT NULL,
                    lifecycle TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    steward_user_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, kpi_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_thresholds (
                    tenant_id TEXT NOT NULL,
                    threshold_id TEXT NOT NULL,
                    kpi_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    target REAL,
                    minimum REAL,
                    maximum REAL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, threshold_id),
                    FOREIGN KEY(tenant_id, kpi_id)
                        REFERENCES kpi_definitions(tenant_id, kpi_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS formula_versions (
                    tenant_id TEXT NOT NULL,
                    formula_version_id TEXT NOT NULL,
                    kpi_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    expression TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    approved_by TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    effective_from TEXT,
                    effective_to TEXT,
                    supersedes_formula_version_id TEXT,
                    is_current INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    PRIMARY KEY (tenant_id, formula_version_id),
                    FOREIGN KEY(tenant_id, kpi_id)
                        REFERENCES kpi_definitions(tenant_id, kpi_id)
                )
            """)
            self._ensure_column(
                cursor,
                "formula_versions",
                "effective_from",
                "TEXT"
            )
            self._ensure_column(
                cursor,
                "formula_versions",
                "effective_to",
                "TEXT"
            )
            self._ensure_column(
                cursor,
                "formula_versions",
                "supersedes_formula_version_id",
                "TEXT"
            )
            self._ensure_column(
                cursor,
                "formula_versions",
                "is_current",
                "INTEGER NOT NULL DEFAULT 1"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_audit_events (
                    tenant_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, event_id)
                )
            """)
            self._create_audit_history_triggers(cursor)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_calculation_results (
                    tenant_id TEXT NOT NULL,
                    result_id TEXT NOT NULL,
                    kpi_id TEXT NOT NULL,
                    formula_version_id TEXT NOT NULL,
                    formula_version_number TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    scope_json TEXT NOT NULL DEFAULT '{}',
                    value REAL,
                    status TEXT NOT NULL,
                    data_quality_status TEXT NOT NULL,
                    source_reference TEXT,
                    calculation_run_id TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, result_id),
                    FOREIGN KEY(tenant_id, kpi_id)
                        REFERENCES kpi_definitions(tenant_id, kpi_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS source_registry (
                    tenant_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_owner TEXT NOT NULL,
                    source_steward TEXT NOT NULL,
                    allowed_entity_scopes_json TEXT NOT NULL DEFAULT '[]',
                    required_fields_json TEXT NOT NULL DEFAULT '[]',
                    numeric_fields_json TEXT NOT NULL DEFAULT '[]',
                    freshness_threshold_hours INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, source_type)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operational_sources (
                    tenant_id TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_reference TEXT,
                    source_version TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    period_start TEXT,
                    period_end TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    validation_status TEXT NOT NULL,
                    data_quality_status TEXT NOT NULL,
                    metric_values_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, source_record_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS source_validation_events (
                    tenant_id TEXT NOT NULL,
                    validation_event_id TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    data_quality_status TEXT NOT NULL,
                    quality_issues_json TEXT NOT NULL DEFAULT '[]',
                    message TEXT,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, validation_event_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_definitions (
                    tenant_id TEXT NOT NULL,
                    risk_definition_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    lifecycle TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    steward_user_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, risk_definition_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_rule_versions (
                    tenant_id TEXT NOT NULL,
                    rule_version_id TEXT NOT NULL,
                    risk_definition_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    handler_key TEXT NOT NULL,
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    approved_by TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    effective_from TEXT,
                    effective_to TEXT,
                    supersedes_rule_version_id TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    PRIMARY KEY (tenant_id, rule_version_id),
                    FOREIGN KEY(tenant_id, risk_definition_id)
                        REFERENCES risk_definitions(tenant_id, risk_definition_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_assessment_results (
                    tenant_id TEXT NOT NULL,
                    result_id TEXT NOT NULL,
                    risk_definition_id TEXT NOT NULL,
                    rule_version_id TEXT NOT NULL,
                    rule_version_number TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    risk_score REAL,
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    source_reference TEXT,
                    assessment_run_id TEXT NOT NULL,
                    risk_definition_version TEXT,
                    kpi_result_ids_json TEXT NOT NULL DEFAULT '[]',
                    formula_versions_json TEXT NOT NULL DEFAULT '[]',
                    source_record_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_validation_lineage_json TEXT NOT NULL DEFAULT '{}',
                    lineage_id TEXT,
                    assessed_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (tenant_id, result_id),
                    FOREIGN KEY(tenant_id, risk_definition_id)
                        REFERENCES risk_definitions(tenant_id, risk_definition_id)
                )
            """)
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "risk_score",
                "REAL"
            )
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "risk_definition_version",
                "TEXT"
            )
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "kpi_result_ids_json",
                "TEXT NOT NULL DEFAULT '[]'"
            )
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "formula_versions_json",
                "TEXT NOT NULL DEFAULT '[]'"
            )
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "source_record_ids_json",
                "TEXT NOT NULL DEFAULT '[]'"
            )
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "source_validation_lineage_json",
                "TEXT NOT NULL DEFAULT '{}'"
            )
            self._ensure_column(
                cursor,
                "risk_assessment_results",
                "lineage_id",
                "TEXT"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operational_impact_definitions (
                    tenant_id TEXT NOT NULL,
                    impact_definition_id TEXT NOT NULL,
                    impact_definition_version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    impact_category TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    steward TEXT NOT NULL,
                    status TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    PRIMARY KEY (
                        tenant_id,
                        impact_definition_id,
                        impact_definition_version
                    )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operational_impact_factors (
                    tenant_id TEXT NOT NULL,
                    impact_factor_id TEXT NOT NULL,
                    impact_factor_version TEXT NOT NULL,
                    impact_definition_id TEXT NOT NULL,
                    impact_definition_version TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source_reference TEXT NOT NULL,
                    weight REAL NOT NULL,
                    direction TEXT NOT NULL,
                    threshold_version TEXT NOT NULL,
                    threshold_min REAL NOT NULL,
                    threshold_max REAL NOT NULL,
                    owner TEXT NOT NULL,
                    steward TEXT NOT NULL,
                    status TEXT NOT NULL,
                    effective_date TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    PRIMARY KEY (
                        tenant_id,
                        impact_factor_id,
                        impact_factor_version
                    ),
                    FOREIGN KEY (
                        tenant_id,
                        impact_definition_id,
                        impact_definition_version
                    ) REFERENCES operational_impact_definitions (
                        tenant_id,
                        impact_definition_id,
                        impact_definition_version
                    )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operational_impact_assessments (
                    tenant_id TEXT NOT NULL,
                    impact_assessment_id TEXT NOT NULL,
                    impact_definition_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    assessment_period_start TEXT NOT NULL,
                    assessment_period_end TEXT NOT NULL,
                    impact_score REAL NOT NULL,
                    impact_level TEXT NOT NULL,
                    impact_definition_version TEXT NOT NULL,
                    impact_factor_ids_json TEXT NOT NULL,
                    impact_factor_versions_json TEXT NOT NULL,
                    threshold_versions_json TEXT NOT NULL,
                    weight_snapshots_json TEXT NOT NULL,
                    factor_score_snapshots_json TEXT NOT NULL,
                    source_kpi_result_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_risk_result_ids_json TEXT NOT NULL DEFAULT '[]',
                    lineage_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, impact_assessment_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_priority_assessments (
                    tenant_id TEXT NOT NULL,
                    priority_assessment_id TEXT NOT NULL,
                    risk_result_id TEXT NOT NULL,
                    risk_definition_version TEXT NOT NULL,
                    risk_rule_version TEXT NOT NULL,
                    impact_assessment_id TEXT NOT NULL,
                    impact_definition_version TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    risk_score_snapshot REAL NOT NULL,
                    impact_score_snapshot REAL NOT NULL,
                    priority_score REAL NOT NULL,
                    priority_level TEXT NOT NULL,
                    priority_reason TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, priority_assessment_id),
                    FOREIGN KEY (tenant_id, impact_assessment_id)
                        REFERENCES operational_impact_assessments (
                            tenant_id,
                            impact_assessment_id
                        )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operational_impact_timeline_events (
                    tenant_id TEXT NOT NULL,
                    timeline_event_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    impact_assessment_id TEXT NOT NULL,
                    priority_assessment_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    material_change_reason TEXT NOT NULL,
                    impact_level_snapshot TEXT NOT NULL,
                    priority_level_snapshot TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, timeline_event_id),
                    UNIQUE (
                        tenant_id,
                        priority_assessment_id,
                        event_type
                    )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_opportunities (
                    tenant_id TEXT NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    opportunity_type TEXT NOT NULL,
                    business_reason TEXT NOT NULL,
                    evidence_pack_id TEXT NOT NULL,
                    risk_result_id TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, opportunity_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coaching_sessions (
                    tenant_id TEXT NOT NULL,
                    coaching_session_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    session_owner_id TEXT NOT NULL,
                    performance_opportunity_id TEXT NOT NULL,
                    evidence_pack_id TEXT NOT NULL,
                    evidence_version_snapshot TEXT NOT NULL,
                    evidence_artifact_ids_snapshot_json TEXT NOT NULL DEFAULT '[]',
                    risk_result_id TEXT NOT NULL,
                    risk_score_snapshot REAL NOT NULL,
                    risk_level_snapshot TEXT NOT NULL,
                    risk_classification_snapshot TEXT NOT NULL,
                    risk_definition_version TEXT NOT NULL,
                    risk_rule_version TEXT NOT NULL,
                    coaching_version TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, coaching_session_id),
                    FOREIGN KEY (tenant_id, performance_opportunity_id)
                        REFERENCES performance_opportunities(
                            tenant_id,
                            opportunity_id
                        )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coaching_commitments (
                    tenant_id TEXT NOT NULL,
                    commitment_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, commitment_id),
                    FOREIGN KEY (tenant_id, session_id)
                        REFERENCES coaching_sessions(
                            tenant_id,
                            coaching_session_id
                        )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coaching_followups (
                    tenant_id TEXT NOT NULL,
                    followup_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    commitment_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome TEXT NOT NULL DEFAULT '',
                    lineage_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, followup_id),
                    FOREIGN KEY (tenant_id, session_id)
                        REFERENCES coaching_sessions(
                            tenant_id,
                            coaching_session_id
                        ),
                    FOREIGN KEY (tenant_id, commitment_id)
                        REFERENCES coaching_commitments(
                            tenant_id,
                            commitment_id
                        )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coaching_notes (
                    tenant_id TEXT NOT NULL,
                    note_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    visibility_level TEXT NOT NULL,
                    content_reference TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, note_id),
                    FOREIGN KEY (tenant_id, session_id)
                        REFERENCES coaching_sessions(
                            tenant_id,
                            coaching_session_id
                        )
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_timeline_events (
                    tenant_id TEXT NOT NULL,
                    timeline_event_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_source TEXT NOT NULL,
                    source_entity_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, timeline_event_id),
                    UNIQUE (
                        tenant_id,
                        employee_id,
                        event_type,
                        event_source,
                        source_entity_id
                    )
                )
            """)

            self._create_performance_history_triggers(cursor)
            self._create_operational_impact_history_triggers(cursor)
            self._create_pci_persistence_triggers(cursor)

            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")

    def _initialize_legacy_tables(self, cursor):
        if (
            self._table_exists(cursor, "agents")
            and not self._column_exists(cursor, "agents", "tenant_id")
        ):
            self._migrate_legacy_tables(cursor)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                tenant_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                employee_id TEXT,
                name TEXT,
                email TEXT,
                nice_name TEXT,
                cxone_name TEXT,
                status TEXT,
                supervisor TEXT,
                PRIMARY KEY (tenant_id, agent_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_aliases (
                tenant_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                PRIMARY KEY (tenant_id, alias),
                FOREIGN KEY (tenant_id, agent_id)
                    REFERENCES agents(tenant_id, agent_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS surveys (
                tenant_id TEXT NOT NULL,
                contact_id TEXT NOT NULL,
                agent_id TEXT,
                agent_name TEXT,
                score REAL,
                csat REAL,
                comment TEXT,
                survey_date TEXT,
                brand TEXT,
                media_type TEXT,
                top_reason TEXT,
                disposition TEXT,
                PRIMARY KEY (tenant_id, contact_id),
                FOREIGN KEY (tenant_id, agent_id)
                    REFERENCES agents(tenant_id, agent_id)
            )
        """)

    def _migrate_legacy_tables(self, cursor):
        legacy_tables = [
            table_name
            for table_name in ("surveys", "agent_aliases", "agents")
            if self._table_exists(cursor, table_name)
        ]
        for table_name in legacy_tables:
            cursor.execute(
                f"ALTER TABLE {table_name} "
                f"RENAME TO {table_name}_pre_tenant"
            )

        self._initialize_legacy_tables(cursor)

        cursor.execute("""
            INSERT INTO agents (
                tenant_id,
                agent_id,
                employee_id,
                name,
                email,
                nice_name,
                cxone_name,
                status,
                supervisor
            )
            SELECT ?, agent_id, employee_id, name, email, nice_name,
                   cxone_name, status, supervisor
            FROM agents_pre_tenant
        """, (self.legacy_tenant_id,))

        if "agent_aliases" in legacy_tables:
            cursor.execute("""
                INSERT INTO agent_aliases (tenant_id, alias, agent_id)
                SELECT ?, alias, agent_id
                FROM agent_aliases_pre_tenant
            """, (self.legacy_tenant_id,))

        if "surveys" in legacy_tables:
            cursor.execute("""
                INSERT INTO surveys (
                    tenant_id,
                    contact_id,
                    agent_id,
                    agent_name,
                    score,
                    csat,
                    comment,
                    survey_date,
                    brand,
                    media_type,
                    top_reason,
                    disposition
                )
                SELECT ?, contact_id, agent_id, agent_name, score, csat,
                       comment, survey_date, brand, media_type, top_reason,
                       disposition
                FROM surveys_pre_tenant
            """, (self.legacy_tenant_id,))

        for table_name in legacy_tables:
            cursor.execute(f"DROP TABLE {table_name}_pre_tenant")

    def _table_exists(self, cursor, table_name):
        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None

    def _column_exists(self, cursor, table_name, column_name):
        cursor.execute(f"PRAGMA table_info({table_name})")
        return any(row[1] == column_name for row in cursor.fetchall())

    def _create_audit_history_triggers(self, cursor):
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_kpi_audit_updates
            BEFORE UPDATE ON kpi_audit_events
            BEGIN
                SELECT RAISE(ABORT, 'Audit events are append-only.');
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_kpi_audit_deletes
            BEFORE DELETE ON kpi_audit_events
            BEGIN
                SELECT RAISE(ABORT, 'Audit events are append-only.');
            END
        """)

    def _create_pci_persistence_triggers(self, cursor):
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        table_names = [row[0] for row in cursor.fetchall()]

        for table_name in table_names:
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            text_columns = [
                row[1]
                for row in cursor.fetchall()
                if "TEXT" in str(row[2]).upper()
            ]
            if not text_columns:
                continue

            unsafe_condition = " OR ".join(
                f'pci_persistence_safe(NEW."{column_name}") = 0'
                for column_name in text_columns
            )
            for operation in ("INSERT", "UPDATE"):
                trigger_name = (
                    f"pci_prevent_{operation.lower()}_{table_name}"
                )
                cursor.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS "{trigger_name}"
                    BEFORE {operation} ON "{table_name}"
                    WHEN {unsafe_condition}
                    BEGIN
                        SELECT RAISE(
                            ABORT,
                            'PCI data persistence prohibited.'
                        );
                    END
                """)

    def _ensure_column(
        self,
        cursor,
        table_name,
        column_name,
        column_definition
    ):
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE {table_name} "
                f"ADD COLUMN {column_name} {column_definition}"
            )

    def _create_performance_history_triggers(self, cursor):
        protected_tables = [
            "performance_opportunities",
            "coaching_sessions",
            "coaching_commitments",
            "coaching_followups",
            "coaching_notes",
            "performance_timeline_events",
        ]
        for table_name in protected_tables:
            cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS no_delete_{table_name}
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Performance management records cannot be deleted.'
                    );
                END
            """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_opportunity_history
            BEFORE UPDATE ON performance_opportunities
            WHEN
                OLD.tenant_id IS NOT NEW.tenant_id OR
                OLD.opportunity_id IS NOT NEW.opportunity_id OR
                OLD.employee_id IS NOT NEW.employee_id OR
                OLD.opportunity_type IS NOT NEW.opportunity_type OR
                OLD.business_reason IS NOT NEW.business_reason OR
                OLD.evidence_pack_id IS NOT NEW.evidence_pack_id OR
                OLD.risk_result_id IS NOT NEW.risk_result_id OR
                OLD.lineage_id IS NOT NEW.lineage_id OR
                OLD.created_by IS NOT NEW.created_by OR
                OLD.created_at IS NOT NEW.created_at
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Historical opportunity fields are immutable.'
                );
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_coaching_session_snapshots
            BEFORE UPDATE ON coaching_sessions
            WHEN
                OLD.tenant_id IS NOT NEW.tenant_id OR
                OLD.coaching_session_id IS NOT NEW.coaching_session_id OR
                OLD.employee_id IS NOT NEW.employee_id OR
                OLD.session_owner_id IS NOT NEW.session_owner_id OR
                OLD.performance_opportunity_id
                    IS NOT NEW.performance_opportunity_id OR
                OLD.evidence_pack_id IS NOT NEW.evidence_pack_id OR
                OLD.evidence_version_snapshot
                    IS NOT NEW.evidence_version_snapshot OR
                OLD.evidence_artifact_ids_snapshot_json
                    IS NOT NEW.evidence_artifact_ids_snapshot_json OR
                OLD.risk_result_id IS NOT NEW.risk_result_id OR
                OLD.risk_score_snapshot IS NOT NEW.risk_score_snapshot OR
                OLD.risk_level_snapshot IS NOT NEW.risk_level_snapshot OR
                OLD.risk_classification_snapshot
                    IS NOT NEW.risk_classification_snapshot OR
                OLD.risk_definition_version
                    IS NOT NEW.risk_definition_version OR
                OLD.risk_rule_version IS NOT NEW.risk_rule_version OR
                OLD.coaching_version IS NOT NEW.coaching_version OR
                OLD.lineage_id IS NOT NEW.lineage_id OR
                OLD.created_by IS NOT NEW.created_by OR
                OLD.created_at IS NOT NEW.created_at
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Coaching session snapshots are immutable.'
                );
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_commitment_history
            BEFORE UPDATE ON coaching_commitments
            WHEN
                OLD.tenant_id IS NOT NEW.tenant_id OR
                OLD.commitment_id IS NOT NEW.commitment_id OR
                OLD.session_id IS NOT NEW.session_id OR
                OLD.employee_id IS NOT NEW.employee_id OR
                OLD.description IS NOT NEW.description OR
                OLD.target_date IS NOT NEW.target_date OR
                OLD.lineage_id IS NOT NEW.lineage_id OR
                OLD.created_by IS NOT NEW.created_by OR
                OLD.created_at IS NOT NEW.created_at
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Historical commitment fields are immutable.'
                );
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_followup_history
            BEFORE UPDATE ON coaching_followups
            WHEN
                OLD.tenant_id IS NOT NEW.tenant_id OR
                OLD.followup_id IS NOT NEW.followup_id OR
                OLD.session_id IS NOT NEW.session_id OR
                OLD.commitment_id IS NOT NEW.commitment_id OR
                OLD.reviewer_id IS NOT NEW.reviewer_id OR
                OLD.lineage_id IS NOT NEW.lineage_id OR
                OLD.created_by IS NOT NEW.created_by OR
                OLD.created_at IS NOT NEW.created_at
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Historical follow-up fields are immutable.'
                );
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_coaching_notes
            BEFORE UPDATE ON coaching_notes
            BEGIN
                SELECT RAISE(ABORT, 'Coaching notes are immutable.');
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_performance_timeline
            BEFORE UPDATE ON performance_timeline_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Performance timeline events are immutable.'
                );
            END
        """)

    def _create_operational_impact_history_triggers(self, cursor):
        immutable_tables = [
            "operational_impact_assessments",
            "risk_priority_assessments",
            "operational_impact_timeline_events",
        ]
        protected_tables = [
            "operational_impact_definitions",
            "operational_impact_factors",
            *immutable_tables,
        ]
        for table_name in protected_tables:
            cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS no_delete_{table_name}
                BEFORE DELETE ON {table_name}
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Operational Impact records cannot be deleted.'
                    );
                END
            """)
        for table_name in immutable_tables:
            cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS immutable_{table_name}
                BEFORE UPDATE ON {table_name}
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Operational Impact history is immutable.'
                    );
                END
            """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_operational_impact_definition
            BEFORE UPDATE ON operational_impact_definitions
            WHEN OLD.impact_definition_id IS NOT NEW.impact_definition_id
              OR OLD.impact_definition_version
                    IS NOT NEW.impact_definition_version
              OR OLD.tenant_id IS NOT NEW.tenant_id
              OR OLD.name IS NOT NEW.name
              OR OLD.description IS NOT NEW.description
              OR OLD.impact_category IS NOT NEW.impact_category
              OR OLD.owner IS NOT NEW.owner
              OR OLD.steward IS NOT NEW.steward
              OR OLD.effective_date IS NOT NEW.effective_date
              OR OLD.created_by IS NOT NEW.created_by
              OR OLD.created_at IS NOT NEW.created_at
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Operational Impact definition versions are immutable.'
                );
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS immutable_operational_impact_factor
            BEFORE UPDATE ON operational_impact_factors
            WHEN OLD.impact_factor_id IS NOT NEW.impact_factor_id
              OR OLD.impact_factor_version IS NOT NEW.impact_factor_version
              OR OLD.tenant_id IS NOT NEW.tenant_id
              OR OLD.impact_definition_id IS NOT NEW.impact_definition_id
              OR OLD.impact_definition_version
                    IS NOT NEW.impact_definition_version
              OR OLD.name IS NOT NEW.name
              OR OLD.description IS NOT NEW.description
              OR OLD.source_reference IS NOT NEW.source_reference
              OR OLD.weight IS NOT NEW.weight
              OR OLD.direction IS NOT NEW.direction
              OR OLD.threshold_version IS NOT NEW.threshold_version
              OR OLD.threshold_min IS NOT NEW.threshold_min
              OR OLD.threshold_max IS NOT NEW.threshold_max
              OR OLD.owner IS NOT NEW.owner
              OR OLD.steward IS NOT NEW.steward
              OR OLD.effective_date IS NOT NEW.effective_date
              OR OLD.created_by IS NOT NEW.created_by
              OR OLD.created_at IS NOT NEW.created_at
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Operational Impact factor versions are immutable.'
                );
            END
        """)
