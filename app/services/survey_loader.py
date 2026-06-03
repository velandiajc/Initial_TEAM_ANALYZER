import pandas as pd

from app.models.survey import Survey


class SurveyLoader:
    def __init__(self, agent_registry):
        self.agent_registry = agent_registry

    def load_from_csv(self, file_path):
        df = pd.read_csv(file_path, encoding="utf-8-sig")

        surveys = []

        for _, row in df.iterrows():
            agent = self.agent_registry.find_agent(row.get("agentname"))

            if agent is None:
                agent_id = str(row.get("agentno", "")).strip()
            else:
                agent_id = agent.agent_id

            survey = Survey(
                contact_id=str(row.get("contactid", "")).strip(),
                agent_id=agent_id,
                agent_name=str(row.get("agentname", "")).strip(),
                score=float(row.get("OSAT", 0)),
                comment=str(row.get("OSAT Score Comment", "")).strip(),
                survey_date=str(row.get("Date of Survey", "")).strip(),
                brand=str(row.get("brand", "")).strip(),
                media_type=str(row.get("media_type_name", "")).strip(),
                top_reason=str(row.get("Top Reason Call", "")).strip(),
                disposition=str(row.get("disposition_name", "")).strip(),
            )

            surveys.append(survey)

        return surveys
    
