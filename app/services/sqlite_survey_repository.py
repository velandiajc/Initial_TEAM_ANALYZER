class SQLiteSurveyRepository:
    def __init__(self, database_service):
        self.database_service = database_service

    def upsert_survey(self, survey):
        csat = float(survey.score) * 10

        with self.database_service.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO surveys (
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                survey.contact_id,
                survey.agent_id,
                survey.agent_name,
                survey.score,
                csat,
                survey.comment,
                survey.survey_date,
                survey.brand,
                survey.media_type,
                survey.top_reason,
                survey.disposition
            ))

            conn.commit()

    def all_surveys(self):
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
            """)

            return cursor.fetchall()