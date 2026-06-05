import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.agent_scorecard_service import AgentScorecardService


DEFAULT_WORKBOOK_PATH = (
    PROJECT_ROOT / "Data" / "raw" / "workbooks" / "Team_JV_MAY.xlsx"
)
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "Reports" / "Sprint_1_Demos" / "agent_scorecards.md"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate supervisor agent scorecards from the workbook Roaster "
            "sheet."
        )
    )
    parser.add_argument(
        "workbook_path",
        nargs="?",
        default=str(DEFAULT_WORKBOOK_PATH),
        help=(
            "Optional workbook path. Defaults to "
            "Data/raw/workbooks/Team_JV_MAY.xlsx."
        )
    )
    parser.add_argument(
        "--sheet",
        default=AgentScorecardService.DEFAULT_SHEET_NAME,
        help="Workbook sheet to use. Defaults to Roaster."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=(
            "Markdown output path. Defaults to "
            "Reports/Sprint_1_Demos/agent_scorecards.md."
        )
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        service = AgentScorecardService()
        report = service.write_report(
            args.workbook_path,
            args.output,
            args.sheet
        )
        print(
            "Agent scorecards created: "
            f"{Path(args.output)} "
            f"({len(report.scorecards)} scorecards)"
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
