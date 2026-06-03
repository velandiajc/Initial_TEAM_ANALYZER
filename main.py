import argparse
import asyncio
import argparse
from app.services.cleanup_service import CleanupService
from app.utils.file_finder import FileFinder

from app.services.cleanup_service import CleanupService
from app.services.database_service import DatabaseService
from app.services.sqlite_agent_repository import SQLiteAgentRepository
from app.services.sqlite_survey_repository import SQLiteSurveyRepository
from app.services.sqlite_agent_discovery_service import SQLiteAgentDiscoveryService
from app.services.agent_registry import AgentRegistry
from app.services.survey_loader import SurveyLoader
from app.services.survey_insight_service import SurveyInsightService


DB_PATH = "Data/database/team_analyzer.db"
SURVEY_FOLDER = "Data/raw/surveys"


async def run_cleanup(reset: bool):
    cleanup = CleanupService()

    if reset:
        print("Running full cleanup...")
        await asyncio.to_thread(cleanup.run_full_cleanup)
    else:
        await asyncio.to_thread(cleanup.run_light_cleanup)


async def initialize_database():
    database = DatabaseService(DB_PATH)
    await asyncio.to_thread(database.initialize)
    return database


async def find_latest_survey():
    latest_survey = await asyncio.to_thread(
        FileFinder.latest_csv,
        SURVEY_FOLDER
    )

    print(f"Latest survey file found: {latest_survey.name}")

    return latest_survey


async def load_surveys(latest_survey):
    registry = AgentRegistry()
    survey_loader = SurveyLoader(registry)

    surveys = await asyncio.to_thread(
        survey_loader.load_from_csv,
        latest_survey
    )

    print(f"Loaded {len(surveys)} surveys from CSV")

    return surveys


async def discover_agents(database, surveys):
    agent_repo = SQLiteAgentRepository(database)

    discovery = SQLiteAgentDiscoveryService(
        agent_repo
    )

    result = await asyncio.to_thread(
        discovery.discover_from_surveys,
        surveys
    )

    print("SQLite agent discovery completed.")
    print(result)

    return result


async def save_surveys(database, surveys):
    agent_repo = SQLiteAgentRepository(database)
    survey_repo = SQLiteSurveyRepository(database)

    def save_all():
        for survey in surveys:
            matched_agent_id = agent_repo.find_agent_id(
                survey.agent_id
            )

            if matched_agent_id:
                survey.agent_id = matched_agent_id

            survey_repo.upsert_survey(survey)

    await asyncio.to_thread(save_all)

    print(f"SQLite survey load completed: {len(surveys)} surveys")


async def create_survey_insights(surveys):
    registry = AgentRegistry()
    insight_service = SurveyInsightService(
        surveys,
        registry
    )

    report_path = await asyncio.to_thread(
        insight_service.export_markdown_report,
        "Reports/survey_insights.md"
    )

    print(f"Survey insights report created: {report_path}")


async def run_pipeline(reset: bool):
    await run_cleanup(reset)

    database = await initialize_database()

    latest_survey = await find_latest_survey()

    surveys = await load_surveys(latest_survey)

    await discover_agents(database, surveys)

    await save_surveys(database, surveys)

    await create_survey_insights(surveys)

    print("")
    print("TEAM_ANALYZER pipeline completed.")
    print(f"Database: {DB_PATH}")

def main(reset=False):

    cleanup = CleanupService()

    if reset:
        print("Running full cleanup...")
        cleanup.run_full_cleanup()
    else:
        cleanup.run_light_cleanup()

    # aquí sigue tu pipeline actual

def parse_args():
    parser = argparse.ArgumentParser(
        description="TEAM_ANALYZER - CX survey and coaching analytics pipeline"
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Deletes generated database, reports, cache and temporary outputs before running."
    )

    return parser.parse_args()

from pathlib import Path

print(
    Path(
        "app/prompts/survey_insights_prompt.md"
    ).exists()
)

if __name__ == "__main__":
    args = parse_args()

    asyncio.run(
        run_pipeline(
            reset=args.reset
        )
    )
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Deletes generated reports, database, cache and temporary outputs before running."
    )

    args = parser.parse_args()

    main(reset=args.reset)
