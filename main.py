import argparse
import asyncio
import os
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.services.agent_registry import AgentRegistry
from app.services.cleanup_service import CleanupService
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.operational_intake_service import OperationalIntakeService
from app.services.sqlite_agent_discovery_service import SQLiteAgentDiscoveryService
from app.services.sqlite_agent_repository import SQLiteAgentRepository
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_operational_intake_repository import (
    SQLiteOperationalIntakeRepository,
)
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


def create_local_context():
    return TenantContext(
        tenant_id=os.getenv("TEAM_ANALYZER_TENANT_ID", "legacy-local"),
        user_id=os.getenv("TEAM_ANALYZER_USER_ID", "local-operator"),
        roles={GovernanceRole.GOVERNANCE_ADMIN.value},
    )


async def initialize_database(context):
    database = DatabaseService(
        DB_PATH,
        legacy_tenant_id=context.tenant_id,
    )
    await asyncio.to_thread(database.initialize)
    audit_service = KPIAuditService(
        SQLiteKPIAuditRepository(database)
    )
    return database, audit_service


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


async def load_surveys(context, audit_service, latest_survey):
    registry = AgentRegistry()
    survey_loader = SurveyLoader(registry, audit_service)

    surveys = await asyncio.to_thread(
        survey_loader.load_from_csv,
        context,
        latest_survey
    )

    if survey_loader.last_survey_type:
        print(f"Detected survey type: {survey_loader.last_survey_type}")

    print(f"Loaded {len(surveys)} surveys from CSV")

    return surveys


async def discover_agents(context, database, audit_service, surveys):
    agent_repo = SQLiteAgentRepository(database, audit_service)

    discovery = SQLiteAgentDiscoveryService(
        agent_repo,
        audit_service,
    )

    result = await asyncio.to_thread(
        discovery.discover_from_surveys,
        context,
        surveys
    )

    print("SQLite agent discovery completed.")
    print(result)

    return result


async def save_surveys(context, database, audit_service, surveys):
    agent_repo = SQLiteAgentRepository(database, audit_service)
    survey_repo = SQLiteSurveyRepository(database, audit_service)

    def save_all():
        for survey in surveys:
            matched_agent_id = agent_repo.find_agent_id(
                context,
                survey.agent_id
            )

            if matched_agent_id:
                survey.agent_id = matched_agent_id

            survey_repo.upsert_survey(context, survey)

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
    context = create_local_context()
    with timed_step("setup"):
        await run_cleanup(reset)
        ensure_local_folders()
        database, audit_service = await initialize_database(context)

    with timed_step("file discovery"):
        latest_survey = await find_latest_survey()

    with timed_step("CSV loading"):
        surveys = await load_surveys(
            context,
            audit_service,
            latest_survey,
        )

    with timed_step("agent discovery"):
        await discover_agents(
            context,
            database,
            audit_service,
            surveys,
        )

    with timed_step("survey persistence"):
        await save_surveys(
            context,
            database,
            audit_service,
            surveys,
        )

    insight_service = create_survey_insight_service(surveys)

    with timed_step("insight generation"):
        insights = await build_survey_insights(insight_service)

    with timed_step("markdown export"):
        await export_survey_insights(insight_service, insights)

    print("")
    print("TEAM_ANALYZER pipeline completed.")
    print(f"Database: {DB_PATH}")


async def run_operational_intake(file_path, reset=False):
    context = create_local_context()
    with timed_step("setup"):
        await run_cleanup(reset)
        ensure_local_folders()
        database, audit_service = await initialize_database(context)

    with timed_step("operational intake"):
        repository = SQLiteOperationalIntakeRepository(
            database,
            audit_service,
        )
        service = OperationalIntakeService(
            repository,
            audit_service,
        )
        run, report = await asyncio.to_thread(
            service.run_from_file,
            context,
            file_path,
            REPORTS_FOLDER,
        )

    print("")
    print("Operational Intake completed.")
    print(f"Run ID: {run.run_id}")
    print(f"Detractor Count: {run.detractor_count}")
    print("Priority Ranking:")
    if not run.priorities:
        print("- No detractor priorities found.")
    else:
        for priority in run.priorities:
            print(
                f"- {priority.priority_rank}. {priority.driver} "
                f"(detractors={priority.detractor_count}, "
                f"impact_score={priority.impact_score}, "
                f"impact_rank={priority.impact_rank})"
            )
    print(f"Parity Report: {report.report_path}")
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
    parser.add_argument(
        "--intake",
        help="Runs OA-1 operational intake for a CSAT export file."
    )

    return parser.parse_args()


def main():
    args = parse_args()

    try:
        if args.intake:
            asyncio.run(
                run_operational_intake(
                    file_path=args.intake,
                    reset=args.reset,
                )
            )
        else:
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
