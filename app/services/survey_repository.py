class SurveyRepository:
    def __init__(self):
        self.surveys = {}

    def add(self, survey):
        self.surveys[survey.contact_id] = survey

    def get(self, contact_id):
        return self.surveys.get(str(contact_id))

    def get_by_agent(self, agent_id):
        return [
            survey
            for survey in self.surveys.values()
            if survey.agent_id == str(agent_id)
        ]

    def all_surveys(self):
        return list(self.surveys.values())
        