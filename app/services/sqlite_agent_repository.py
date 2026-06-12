from app.core.permissions import KPIPermission
from app.services.legacy_governance import LegacyGovernanceSupport


class SQLiteAgentRepository(LegacyGovernanceSupport):
    def __init__(self, database_service, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.database_service = database_service

    def upsert_agent(self, context, agent):
        context = self.require_context(context)
        self.require_permission(
            context,
            KPIPermission.MANAGE_AGENT_RECORDS,
            "agent",
            str(agent.get("agent_id", "new")),
        )
        agent_id = str(agent.get("agent_id", "")).strip()
        if not agent_id:
            raise ValueError("agent_id is required.")

        with self.database_service.connect() as conn:
            cursor = conn.cursor()

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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, agent_id) DO UPDATE SET
                    employee_id = excluded.employee_id,
                    name = excluded.name,
                    email = excluded.email,
                    nice_name = excluded.nice_name,
                    cxone_name = excluded.cxone_name,
                    status = excluded.status,
                    supervisor = excluded.supervisor
            """, (
                context.tenant_id,
                agent_id,
                agent.get("employee_id", ""),
                agent.get("name", ""),
                agent.get("email", ""),
                agent.get("nice_name", ""),
                agent.get("cxone_name", ""),
                agent.get("status", "Active"),
                agent.get("supervisor", "")
            ))

            for alias in agent.get("aliases", []):
                cursor.execute("""
                    INSERT INTO agent_aliases (
                        tenant_id,
                        alias,
                        agent_id
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(tenant_id, alias) DO UPDATE SET
                        agent_id = excluded.agent_id
                """, (
                    context.tenant_id,
                    alias.strip().lower(),
                    agent_id,
                ))

            conn.commit()
        self.audit(
            context,
            "AGENT_RECORD_UPSERTED",
            "agent",
            agent_id,
            {"alias_count": len(agent.get("aliases", []))},
        )

    def find_agent_id(self, context, value):
        context = self.require_context(context)
        self.require_permission(
            context,
            KPIPermission.VIEW_AGENT_RECORDS,
            "agent",
            "agent_lookup",
        )
        key = str(value).strip().lower()

        with self.database_service.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT agent_id
                FROM agents
                WHERE tenant_id = ?
                  AND (
                       lower(agent_id) = ?
                    OR lower(employee_id) = ?
                    OR lower(name) = ?
                    OR lower(nice_name) = ?
                    OR lower(cxone_name) = ?
                    OR lower(email) = ?
                  )
            """, (
                context.tenant_id,
                key,
                key,
                key,
                key,
                key,
                key,
            ))

            row = cursor.fetchone()

            if row:
                agent_id = row[0]
            else:
                cursor.execute("""
                    SELECT agent_id
                    FROM agent_aliases
                    WHERE tenant_id = ?
                      AND alias = ?
                """, (
                    context.tenant_id,
                    key,
                ))
                row = cursor.fetchone()
                agent_id = row[0] if row else None

        self.audit(
            context,
            "AGENT_RECORD_LOOKUP",
            "agent",
            agent_id or "not_found",
            {"found": agent_id is not None},
        )
        return agent_id
