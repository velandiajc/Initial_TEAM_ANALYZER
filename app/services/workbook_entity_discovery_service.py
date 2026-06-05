from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.services.workbook_ingestion_service import (
    WorkbookInventory,
    WorksheetInventory,
)


@dataclass
class WorkbookEntityDiscovery:
    sheet_name: str
    entity: str
    columns: list[str]
    confidence: float


@dataclass
class WorkbookEntityDiscoveryReport:
    inventory_path: str
    sheet_count: int
    discoveries: list[WorkbookEntityDiscovery]


class WorkbookEntityDiscoveryService:
    ENTITY_COLUMN_KEYWORDS = {
        "Agent": {
            "agent",
            "agent id",
            "agent name",
            "email",
            "id",
            "name",
            "supervisor",
        },
        "QA": {
            "qa",
            "qa coverage",
            "qa coverage status",
            "qa mtd",
            "qa score",
        },
        "CSAT": {
            "csat",
            "csat mtd",
            "detractor",
            "detractors",
            "dsat",
            "open dsat",
            "osat",
            "osat mtd",
        },
        "Coaching": {
            "coaching",
            "coaching action",
            "coaching focus",
            "coaching needed",
        },
        "Attendance": {
            "absence",
            "absenteeism",
            "attendance",
            "late",
            "tardy",
        },
        "Adherence": {
            "adherence",
            "schedule adherence",
        },
        "Risk": {
            "critical flag",
            "priority score",
            "risk",
            "risk final",
        },
        "Workforce": {
            "aht",
            "headcount",
            "occupancy",
            "shrinkage",
            "staffing",
            "wfm",
            "workforce",
        },
        "Schedule": {
            "end time",
            "schedule",
            "shift",
            "start time",
            "supervisor schedule",
        },
    }

    EXACT_ONLY_KEYWORDS = {
        "agent",
        "email",
        "id",
        "name",
        "qa",
        "risk",
        "supervisor",
    }

    def discover_from_inventory_markdown(
        self,
        inventory_path
    ) -> WorkbookEntityDiscoveryReport:
        path = Path(inventory_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Workbook inventory file not found: {path}"
            )

        inventory = self._parse_inventory_markdown(
            path.read_text(encoding="utf-8"),
            path
        )

        return self.discover(
            inventory,
            inventory_path=path
        )

    def discover(
        self,
        inventory: WorkbookInventory,
        inventory_path=None
    ) -> WorkbookEntityDiscoveryReport:
        discoveries = []

        for sheet in inventory.sheets:
            for entity, keywords in self.ENTITY_COLUMN_KEYWORDS.items():
                columns = self._matching_columns(
                    sheet.column_names,
                    keywords
                )

                if not columns:
                    continue

                discoveries.append(
                    WorkbookEntityDiscovery(
                        sheet_name=sheet.sheet_name,
                        entity=entity,
                        columns=columns,
                        confidence=self._confidence(
                            sheet.sheet_name,
                            entity,
                            columns
                        )
                    )
                )

        return WorkbookEntityDiscoveryReport(
            inventory_path=str(
                Path(inventory_path)
                if inventory_path is not None
                else Path(inventory.workbook_path)
            ),
            sheet_count=inventory.sheet_count,
            discoveries=discoveries
        )

    def render_markdown(
        self,
        report: WorkbookEntityDiscoveryReport
    ) -> str:
        lines = [
            "# Workbook Entity Discovery",
            "",
            f"**Inventory:** {report.inventory_path}",
            f"**Sheet Count:** {report.sheet_count}",
            f"**Discovery Count:** {len(report.discoveries)}",
            "",
        ]

        if not report.discoveries:
            lines.append("No workbook entities discovered.")
            return "\n".join(lines).rstrip() + "\n"

        lines.extend(
            [
                "| Sheet | Entity | Columns | Confidence |",
                "|---|---|---|---|",
            ]
        )

        for discovery in report.discoveries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._escape_markdown_cell(discovery.sheet_name),
                        self._escape_markdown_cell(discovery.entity),
                        self._escape_markdown_cell(
                            ", ".join(discovery.columns)
                        ),
                        f"{discovery.confidence:.2f}",
                    ]
                )
                + " |"
            )

        return "\n".join(lines).rstrip() + "\n"

    def write_report(
        self,
        inventory_path,
        output_path="Reports/workbook_entities.md"
    ) -> WorkbookEntityDiscoveryReport:
        report = self.discover_from_inventory_markdown(inventory_path)
        path = Path(output_path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        path.write_text(
            self.render_markdown(report),
            encoding="utf-8"
        )
        return report

    def _matching_columns(
        self,
        column_names: Iterable[str],
        keywords: set[str]
    ) -> list[str]:
        matches = []

        for column_name in column_names:
            normalized = self._normalize(column_name)

            if not normalized:
                continue

            if self._matches_any_keyword(normalized, keywords):
                matches.append(column_name)

        return matches

    def _matches_any_keyword(
        self,
        normalized_column: str,
        keywords: set[str]
    ) -> bool:
        for keyword in keywords:
            normalized_keyword = self._normalize(keyword)

            if normalized_column == normalized_keyword:
                return True

            if normalized_keyword in self.EXACT_ONLY_KEYWORDS:
                continue

            if normalized_keyword in normalized_column:
                return True

        return False

    def _confidence(
        self,
        sheet_name: str,
        entity: str,
        columns: list[str]
    ) -> float:
        confidence = 0.6 + min(
            len(columns),
            4
        ) * 0.08

        normalized_sheet_name = self._normalize(sheet_name)
        normalized_entity = self._normalize(entity)

        if normalized_entity in normalized_sheet_name:
            confidence += 0.07

        return min(
            confidence,
            0.99
        )

    def _parse_inventory_markdown(
        self,
        markdown: str,
        inventory_path: Path
    ) -> WorkbookInventory:
        workbook_path = ""
        sheet_count = 0
        sheets = []
        current_sheet = None
        in_columns = False

        for raw_line in markdown.splitlines():
            line = raw_line.strip()

            if line.startswith("**Workbook:**"):
                workbook_path = line.replace("**Workbook:**", "").strip()
                continue

            if line.startswith("**Sheet Count:**"):
                sheet_count = int(
                    line.replace("**Sheet Count:**", "").strip()
                )
                continue

            if line.startswith("## Sheet:"):
                if current_sheet is not None:
                    sheets.append(current_sheet)

                current_sheet = {
                    "sheet_name": line.replace("## Sheet:", "").strip(),
                    "row_count": 0,
                    "column_count": 0,
                    "header_row_number": None,
                    "column_names": [],
                }
                in_columns = False
                continue

            if current_sheet is None:
                continue

            if line.startswith("- Row count:"):
                current_sheet["row_count"] = int(
                    line.replace("- Row count:", "").strip()
                )
                continue

            if line.startswith("- Column count:"):
                current_sheet["column_count"] = int(
                    line.replace("- Column count:", "").strip()
                )
                continue

            if line.startswith("- Detected header row:"):
                header_row = line.replace(
                    "- Detected header row:",
                    ""
                ).strip()
                current_sheet["header_row_number"] = (
                    int(header_row)
                    if header_row.isdigit()
                    else None
                )
                continue

            if line == "### Columns":
                in_columns = True
                continue

            if line.startswith("### "):
                in_columns = False
                continue

            if in_columns and line.startswith("- "):
                current_sheet["column_names"].append(line[2:])

        if current_sheet is not None:
            sheets.append(current_sheet)

        worksheet_inventories = [
            WorksheetInventory(
                sheet_name=sheet["sheet_name"],
                row_count=sheet["row_count"],
                column_count=sheet["column_count"],
                header_row_number=sheet["header_row_number"],
                column_names=sheet["column_names"],
                sample_rows=[]
            )
            for sheet in sheets
        ]

        return WorkbookInventory(
            workbook_path=workbook_path or str(inventory_path),
            sheet_count=sheet_count or len(worksheet_inventories),
            sheets=worksheet_inventories
        )

    def _normalize(self, value: str) -> str:
        text = str(value).replace("_", " ").replace("-", " ")
        return " ".join(text.strip().lower().split())

    def _escape_markdown_cell(self, value) -> str:
        text = str(value)
        text = text.replace("\r", " ")
        text = text.replace("\n", " ")
        text = text.replace("|", "\\|")
        return text
