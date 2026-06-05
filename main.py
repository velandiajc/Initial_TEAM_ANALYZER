import argparse
import asyncio
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from app.services.agent_registry import AgentRegistry
from app.services.cleanup_service import CleanupService
from app.services.database_service import DatabaseService
from app.services.sqlite_agent_discovery_service import SQLiteAgentDiscoveryService
from app.services.sqlite_agent_repository import SQLiteAgentRepository
from app.services.sqlite_survey_repository import SQLiteSurveyRepository
from app.services.survey_insight_service import SurveyInsightService
from app.services.survey_loader import SurveyLoader
from app.utils.file_finder import FileFinder


DB_PATH = Path("Data/database/team_analyzer.db")
SURVEY_FOLDER = Path("Data/raw/surveys")
REPORTS_FOLDER = Path("Reports")
SURVEY_INSIGHTS_REPORT = REPORTS_FOLDER / "survey_insights.md"


class NoSurveyCsvFoundError(Exception):
    pass


@contextmanager
def timed_step(step_name):
    started_at = perf_counter()
    print(f"[{step_name}] started")

    try:
        yield
    finally:
        elapsed = perf_counter() - started_at
        print(f"[{step_name}] completed in {elapsed:.2f}s")


def ensure_local_folders():
    SURVEY_FOLDER.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)


async def run_cleanup(reset):
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
    try:
        latest_survey = await asyncio.to_thread(
            FileFinder.latest_csv,
            SURVEY_FOLDER
        )
    except FileNotFoundError as exc:
        raise NoSurveyCsvFoundError(
            "No survey CSV files were found.\n"
            f"Place at least one .csv file in {SURVEY_FOLDER} and run "
            "`python main.py` again."
        ) from exc

    print(f"Latest survey file found: {latest_survey.name}")

    return latest_survey


async def load_surveys(latest_survey):
    registry = AgentRegistry()
    survey_loader = SurveyLoader(registry)

    surveys = await asyncio.to_thread(
        survey_loader.load_from_csv,
        latest_survey
    )

    if survey_loader.last_survey_type:
        print(f"Detected survey type: {survey_loader.last_survey_type}")

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


def create_survey_insight_service(surveys):
    registry = AgentRegistry()
    return SurveyInsightService(
        surveys,
        registry
    )


async def build_survey_insights(insight_service):
    return await asyncio.to_thread(
        insight_service.build_insights
    )


async def export_survey_insights(insight_service, insights):
    report_path = await asyncio.to_thread(
        insight_service.export_markdown_report,
        SURVEY_INSIGHTS_REPORT,
        insights
    )

    print(f"Survey insights report created: {report_path}")


async def run_pipeline(reset):
    with timed_step("setup"):
        await run_cleanup(reset)
        ensure_local_folders()
        database = await initialize_database()

    with timed_step("file discovery"):
        latest_survey = await find_latest_survey()

    with timed_step("CSV loading"):
        surveys = await load_surveys(latest_survey)

    with timed_step("agent discovery"):
        await discover_agents(database, surveys)

    with timed_step("survey persistence"):
        await save_surveys(database, surveys)

    insight_service = create_survey_insight_service(surveys)

    with timed_step("insight generation"):
        insights = await build_survey_insights(insight_service)

    with timed_step("markdown export"):
        await export_survey_insights(insight_service, insights)

    print("")
    print("TEAM_ANALYZER pipeline completed.")
    print(f"Database: {DB_PATH}")


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


def main():
    args = parse_args()

    try:
        asyncio.run(
            run_pipeline(
                reset=args.reset
            )
        )
    except NoSurveyCsvFoundError as exc:
        print("")
        print(exc)


if __name__ == "__main__":
    main()
