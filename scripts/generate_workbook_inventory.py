import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.workbook_ingestion_service import WorkbookIngestionService


WORKBOOK_FOLDER = PROJECT_ROOT / "Data" / "raw" / "workbooks"
REPORTS_FOLDER = PROJECT_ROOT / "Reports"


class NoWorkbookFoundError(Exception):
    pass


def latest_xlsx(folder: Path) -> Path:
    files = list(folder.glob("*.xlsx"))

    if not files:
        raise NoWorkbookFoundError(
            f"No .xlsx files were found in {folder}"
        )

    return max(
        files,
        key=lambda path: path.stat().st_mtime
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Generate workbook inventory and validation reports "
            "for an .xlsx workbook."
        )
    )

    parser.add_argument(
        "workbook_path",
        nargs="?",
        help=(
            "Optional path to an .xlsx workbook. Defaults to the latest "
            "file in Data/raw/workbooks/."
        )
    )

    return parser.parse_args()


def resolve_workbook_path(workbook_path):
    if workbook_path:
        return Path(workbook_path)

    return latest_xlsx(WORKBOOK_FOLDER)


def main():
    args = parse_args()

    try:
        workbook_path = resolve_workbook_path(
            args.workbook_path
        )

        service = WorkbookIngestionService()
        service.write_reports(
            workbook_path,
            REPORTS_FOLDER
        )

        print(
            "Workbook reports created: "
            f"{REPORTS_FOLDER / 'workbook_inventory.md'} and "
            f"{REPORTS_FOLDER / 'workbook_validation.md'}"
        )
    except (FileNotFoundError, ValueError, NoWorkbookFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
