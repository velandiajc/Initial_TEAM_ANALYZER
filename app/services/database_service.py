import sqlite3
from pathlib import Path


class DatabaseService:
    def __init__(self, db_path="Data/database/team_analyzer.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        return sqlite3.connect(self.db_path)

    def initialize(self):
        with self.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    employee_id TEXT,
                    name TEXT,
                    email TEXT,
                    nice_name TEXT,
                    cxone_name TEXT,
                    status TEXT,
                    supervisor TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_aliases (
                    alias TEXT PRIMARY KEY,
                    agent_id TEXT,
                    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS surveys (
                    contact_id TEXT PRIMARY KEY,
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
                    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
                )
            """)

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
                    notes TEXT,
                    PRIMARY KEY (tenant_id, formula_version_id),
                    FOREIGN KEY(tenant_id, kpi_id)
                        REFERENCES kpi_definitions(tenant_id, kpi_id)
                )
            """)

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

            conn.commit()
