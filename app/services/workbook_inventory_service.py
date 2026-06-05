from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class WorksheetInventory:
    sheet_name: str
    row_count: int
    column_count: int
    column_names: list[str]
    sample_rows: list[dict]


@dataclass
class WorkbookInventory:
    workbook_path: str
    sheet_count: int
    sheets: list[WorksheetInventory]


class WorkbookInventoryService:
    SAMPLE_ROW_LIMIT = 5
    CELL_VALUE_LIMIT = 120

    def build_inventory(self, workbook_path) -> WorkbookInventory:
        path = self._validate_workbook_path(workbook_path)

        workbook = pd.ExcelFile(
            path,
            engine="openpyxl"
        )

        sheets = []

        for sheet_name in workbook.sheet_names:
            dataframe = pd.read_excel(
                workbook,
                sheet_name=sheet_name
            )

            column_names = [
                str(column)
                for column in dataframe.columns
            ]

            sheets.append(
                WorksheetInventory(
                    sheet_name=sheet_name,
                    row_count=len(dataframe),
                    column_count=len(dataframe.columns),
                    column_names=column_names,
                    sample_rows=self._sample_rows(dataframe)
                )
            )

        return WorkbookInventory(
            workbook_path=str(path),
            sheet_count=len(sheets),
            sheets=sheets
        )

    def render_markdown(self, inventory: WorkbookInventory) -> str:
        lines = [
            "# Workbook Inventory",
            "",
            f"**Workbook:** {inventory.workbook_path}",
            f"**Sheet Count:** {inventory.sheet_count}",
            "",
        ]

        for sheet in inventory.sheets:
            lines.extend(
                [
                    f"## Sheet: {sheet.sheet_name}",
                    "",
                    f"- Row count: {sheet.row_count}",
                    f"- Column count: {sheet.column_count}",
                    "",
                    "### Columns",
                    "",
                ]
            )

            if sheet.column_names:
                for column_name in sheet.column_names:
                    lines.append(f"- {column_name}")
            else:
                lines.append("No columns.")

            lines.extend(
                [
                    "",
                    "### Sample Rows",
                    "",
                ]
            )

            if sheet.sample_rows:
                lines.extend(
                    self._render_sample_rows(
                        sheet.column_names,
                        sheet.sample_rows
                    )
                )
            else:
                lines.append("No sample rows.")

            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _validate_workbook_path(self, workbook_path) -> Path:
        path = Path(workbook_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Workbook file not found: {path}"
            )

        if path.suffix.lower() != ".xlsx":
            raise ValueError(
                f"Workbook inventory only supports .xlsx files: {path}"
            )

        return path

    def _sample_rows(self, dataframe) -> list[dict]:
        rows = []

        for record in dataframe.head(
            self.SAMPLE_ROW_LIMIT
        ).to_dict(orient="records"):
            rows.append(
                {
                    str(column): self._clean_cell_value(value)
                    for column, value in record.items()
                }
            )

        return rows

    def _clean_cell_value(self, value: Any) -> str:
        try:
            if pd.isna(value):
                return ""
        except TypeError:
            pass

        text = str(value)

        if len(text) > self.CELL_VALUE_LIMIT:
            return text[:self.CELL_VALUE_LIMIT]

        return text

    def _render_sample_rows(
        self,
        column_names: list[str],
        sample_rows: list[dict]
    ) -> list[str]:
        header = [
            self._escape_markdown_cell(column)
            for column in column_names
        ]

        lines = [
            "| " + " | ".join(header) + " |",
            "|" + "|".join("---" for _ in column_names) + "|",
        ]

        for row in sample_rows:
            values = [
                self._escape_markdown_cell(
                    row.get(column, "")
                )
                for column in column_names
            ]
            lines.append(
                "| " + " | ".join(values) + " |"
            )

        return lines

    def _escape_markdown_cell(self, value: Any) -> str:
        text = str(value)
        text = text.replace("\r", " ")
        text = text.replace("\n", " ")
        text = text.replace("|", "\\|")
        return text
