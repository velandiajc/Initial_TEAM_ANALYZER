import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.workbook_inventory_service import WorkbookInventoryService


WORKBOOK_FOLDER = PROJECT_ROOT / "Data" / "raw" / "workbooks"
OUTPUT_PATH = PROJECT_ROOT / "Reports" / "workbook_inventory.md"


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
        description="Generate a Markdown inventory report for an .xlsx workbook."
    )

    parser.add_argument(
        "workbook_path",
        nargs="?",
        help="Optional path to an .xlsx workbook. Defaults to the latest file in Data/raw/workbooks/."
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

        service = WorkbookInventoryService()
        inventory = service.build_inventory(
            workbook_path
        )
        markdown = service.render_markdown(
            inventory
        )

        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        OUTPUT_PATH.write_text(
            markdown,
            encoding="utf-8"
        )

        print(f"Workbook inventory report created: {OUTPUT_PATH}")
    except (FileNotFoundError, ValueError, NoWorkbookFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
