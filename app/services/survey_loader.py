import pandas as pd

from app.core.permissions import KPIPermission
from app.models.survey import Survey
from app.services.legacy_governance import LegacyGovernanceSupport
from app.services.pci_redaction_service import PCIRedactionService
from app.services.survey_normalizer import SurveyNormalizer


class SurveyLoader(LegacyGovernanceSupport):
    def __init__(
        self,
        agent_registry,
        audit_service,
        rbac_service=None,
    ):
        super().__init__(audit_service, rbac_service)
        self.agent_registry = agent_registry
        self.pci_redaction_service = PCIRedactionService()
        self.last_survey_type = None

    def load_from_csv(self, context, file_path):
        context = self.require_context(context)
        self.require_permission(
            context,
            KPIPermission.INGEST_SURVEYS,
            "survey_ingestion",
            "csv_batch",
        )
        self.audit(
            context,
            "SURVEY_INGESTION_STARTED",
            "survey_ingestion",
            "csv_batch",
        )
        df = pd.read_csv(file_path, encoding="utf-8-sig")
        normalizer = SurveyNormalizer(df)
        self.last_survey_type = normalizer.survey_type

        surveys = []

        for row in normalizer.normalize():
            agent = (
                self.agent_registry.find_agent(row["agent_name"])
                or self.agent_registry.find_agent(row["agent_id"])
            )

            if agent is None:
                agent_id = row["agent_id"]
            else:
                agent_id = agent.agent_id

            survey = Survey(
                contact_id=row["contact_id"],
                agent_id=agent_id,
                agent_name=row["agent_name"],
                score=row["score"],
                comment=self.pci_redaction_service.redact(row["comment"]),
                survey_date=row["survey_date"],
                brand=row["brand"],
                media_type=row["media_type"],
                top_reason=row["top_reason"],
                disposition=row["disposition"],
            )

            surveys.append(survey)

        self.audit(
            context,
            "SURVEY_INGESTION_COMPLETED",
            "survey_ingestion",
            "csv_batch",
            {
                "record_count": len(surveys),
                "survey_type": self.last_survey_type or "unknown",
            },
        )
        return surveys
    
