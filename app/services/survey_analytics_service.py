import csv
from collections import defaultdict
from pathlib import Path


class SurveyAnalyticsService:

    def __init__(self, surveys, agent_registry):
        self.surveys = surveys
        self.agent_registry = agent_registry

    def _classify_score(self, score):
        try:
            score = float(score)
        except Exception:
            return "Unknown"

        if score >= 9:
            return "Promoter"

        if score >= 7:
            return "Neutral"

        return "Detractor"

    def build_agent_summary(self):
        grouped = defaultdict(list)

        for survey in self.surveys:
            grouped[survey.agent_id].append(survey)

        summary = []

        for agent_id, agent_surveys in grouped.items():
            agent = self.agent_registry.find_agent(agent_id)

            scores = [
                float(survey.score)
                for survey in agent_surveys
                if survey.score is not None
            ]

            promoters = sum(
                1
                for score in scores
                if score >= 9
            )

            neutrals = sum(
                1
                for score in scores
                if 7 <= score < 9
            )

            detractors = sum(
                1
                for score in scores
                if score < 7
            )

            avg_score = (
                round(sum(scores) / len(scores), 2)
                if scores
                else 0
            )

            latest_comment = ""

            comments = [
                survey.comment
                for survey in agent_surveys
                if survey.comment
                and str(survey.comment).lower() != "nan"
            ]

            if comments:
                latest_comment = comments[-1]

            summary.append(
                {
                    "agent_id": agent_id,
                    "agent_name": agent.name if agent else "",
                    "surveys": len(agent_surveys),
                    "avg_osat": avg_score,
                    "promoters": promoters,
                    "neutrals": neutrals,
                    "detractors": detractors,
                    "latest_comment": latest_comment,
                }
            )

        summary.sort(
            key=lambda row: (
                row["avg_osat"],
                -row["surveys"]
            )
        )

        return summary

    def export_agent_summary(self, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        summary = self.build_agent_summary()

        fieldnames = [
            "agent_id",
            "agent_name",
            "surveys",
            "avg_osat",
            "promoters",
            "neutrals",
            "detractors",
            "latest_comment",
        ]

        with output_path.open(
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()
            writer.writerows(summary)

        return output_path
    