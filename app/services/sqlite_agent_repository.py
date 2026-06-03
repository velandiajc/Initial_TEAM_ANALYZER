class SQLiteAgentRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def upsert_agent(self, agent):
        with self.database_service.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO agents (
                    agent_id,
                    employee_id,
                    name,
                    email,
                    nice_name,
                    cxone_name,
                    status,
                    supervisor
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent["agent_id"],
                agent["employee_id"],
                agent["name"],
                agent.get("email", ""),
                agent.get("nice_name", ""),
                agent.get("cxone_name", ""),
                agent.get("status", "Active"),
                agent.get("supervisor", "")
            ))

            for alias in agent.get("aliases", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO agent_aliases (
                        alias,
                        agent_id
                    )
                    VALUES (?, ?)
                """, (
                    alias.strip().lower(),
                    agent["agent_id"]
                ))

            conn.commit()

    def find_agent_id(self, value):
        key = str(value).strip().lower()

        with self.database_service.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT agent_id
                FROM agents
                WHERE lower(agent_id) = ?
                   OR lower(employee_id) = ?
                   OR lower(name) = ?
                   OR lower(nice_name) = ?
                   OR lower(cxone_name) = ?
                   OR lower(email) = ?
            """, (key, key, key, key, key, key))

            row = cursor.fetchone()

            if row:
                return row[0]

            cursor.execute("""
                SELECT agent_id
                FROM agent_aliases
                WHERE alias = ?
            """, (key,))

            row = cursor.fetchone()

            return row[0] if row else None
        