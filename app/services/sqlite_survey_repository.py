from app.core.permissions import KPIPermission
from app.services.legacy_governance import LegacyGovernanceSupport
from app.services.pci_redaction_service import PCIRedactionService


class SQLiteSurveyRepository(LegacyGovernanceSupport):
    def __init__(self, database_service, audit_service, rbac_service=None):
        super().__init__(audit_service, rbac_service)
        self.database_service = database_service
        self.pci_redaction_service = PCIRedactionService()

    def upsert_survey(self, context, survey):
        context = self.require_context(context)
        self.require_permission(
            context,
            KPIPermission.INGEST_SURVEYS,
            "survey",
            survey.contact_id,
        )
        csat = float(survey.score) * 10

        with self.database_service.connect() as conn:
            cursor = conn.cursor()

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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, contact_id) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    agent_name = excluded.agent_name,
                    score = excluded.score,
                    csat = excluded.csat,
                    comment = excluded.comment,
                    survey_date = excluded.survey_date,
                    brand = excluded.brand,
                    media_type = excluded.media_type,
                    top_reason = excluded.top_reason,
                    disposition = excluded.disposition
            """, (
                context.tenant_id,
                survey.contact_id,
                survey.agent_id,
                survey.agent_name,
                survey.score,
                csat,
                self.pci_redaction_service.redact(survey.comment),
                survey.survey_date,
                survey.brand,
                survey.media_type,
                survey.top_reason,
                survey.disposition
            ))

            conn.commit()
        self.audit(
            context,
            "SURVEY_RECORD_UPSERTED",
            "survey",
            survey.contact_id,
            {
                "agent_id": survey.agent_id,
                "media_type": survey.media_type,
            },
        )

    def all_surveys(self, context):
        context = self.require_context(context)
        self.require_permission(
            context,
            KPIPermission.VIEW_SURVEYS,
            "survey_collection",
            "all",
        )
        with self.database_service.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
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
                FROM surveys
                WHERE tenant_id = ?
                ORDER BY survey_date, contact_id
            """, (context.tenant_id,))

            rows = cursor.fetchall()
        self.audit(
            context,
            "SURVEY_RECORDS_VIEWED",
            "survey_collection",
            "all",
            {"record_count": len(rows)},
        )
        return rows
