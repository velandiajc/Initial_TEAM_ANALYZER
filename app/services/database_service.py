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

            conn.commit()
            