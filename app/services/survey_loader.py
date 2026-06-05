import pandas as pd

from app.models.survey import Survey
from app.services.survey_normalizer import SurveyNormalizer


class SurveyLoader:
    def __init__(self, agent_registry):
        self.agent_registry = agent_registry
        self.last_survey_type = None

    def load_from_csv(self, file_path):
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
                comment=row["comment"],
                survey_date=row["survey_date"],
                brand=row["brand"],
                media_type=row["media_type"],
                top_reason=row["top_reason"],
                disposition=row["disposition"],
            )

            surveys.append(survey)

        return surveys
    
