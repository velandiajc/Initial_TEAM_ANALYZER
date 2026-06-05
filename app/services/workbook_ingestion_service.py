from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class WorksheetInventory:
    sheet_name: str
    row_count: int
    column_count: int
    header_row_number: int | None
    column_names: list[str]
    sample_rows: list[dict]


@dataclass
class WorkbookInventory:
    workbook_path: str
    sheet_count: int
    sheets: list[WorksheetInventory]


@dataclass
class WorkbookValidationIssue:
    sheet_name: str
    issue_type: str
    message: str
    row_number: int | None = None
    column_name: str | None = None
    value: str | None = None


@dataclass
class WorkbookValidationReport:
    workbook_path: str
    issue_count: int
    issues: list[WorkbookValidationIssue]


@dataclass
class WorkbookIngestionResult:
    inventory: WorkbookInventory
    validation: WorkbookValidationReport


class WorkbookIngestionService:
    HEADER_SCAN_LIMIT = 20
    SAMPLE_ROW_LIMIT = 5
    CELL_VALUE_LIMIT = 120

    HEADER_KEYWORDS = {
        "adherence",
        "agent",
        "agent name",
        "attendance",
        "brand",
        "call id",
        "contact id",
        "csat",
        "disposition",
        "id",
        "interaction id",
        "osat",
        "qa",
        "schedule",
        "status",
        "supervisor",
    }

    OSAT_COLUMNS = {
        "osat",
        "osat mtd",
        "avg osat",
        "average osat",
    }
    CSAT_COLUMNS = {
        "csat",
        "csat mtd",
        "avg csat",
        "average csat",
    }
    QA_COLUMNS = {
        "qa",
        "qa mtd",
        "qa score",
        "avg qa",
        "average qa",
    }
    AGENT_NAME_COLUMNS = {
        "agent",
        "agent name",
        "agentname",
        "agent clean",
        "afn",
        "name",
    }
    AGENT_ID_COLUMNS = {
        "agent id",
        "agent_id",
        "agent no",
        "agentno",
        "employee id",
        "ano",
        "icano",
    }

    def ingest(self, workbook_path) -> WorkbookIngestionResult:
        sheets = self._read_workbook(workbook_path)
        inventory = self.build_inventory_from_sheets(
            workbook_path,
            sheets
        )
        validation = self.validate_sheets(
            workbook_path,
            sheets
        )

        return WorkbookIngestionResult(
            inventory=inventory,
            validation=validation
        )

    def build_inventory(self, workbook_path) -> WorkbookInventory:
        sheets = self._read_workbook(workbook_path)
        return self.build_inventory_from_sheets(
            workbook_path,
            sheets
        )

    def validate_workbook(self, workbook_path) -> WorkbookValidationReport:
        sheets = self._read_workbook(workbook_path)
        return self.validate_sheets(
            workbook_path,
            sheets
        )

    def build_inventory_from_sheets(
        self,
        workbook_path,
        sheets: list[dict]
    ) -> WorkbookInventory:
        inventories = []

        for sheet in sheets:
            column_names = sheet["column_names"]
            rows = sheet["rows"]

            inventories.append(
                WorksheetInventory(
                    sheet_name=sheet["sheet_name"],
                    row_count=len(rows),
                    column_count=len(column_names),
                    header_row_number=sheet["header_row_number"],
                    column_names=column_names,
                    sample_rows=self._sample_rows(
                        column_names,
                        rows
                    )
                )
            )

        return WorkbookInventory(
            workbook_path=str(Path(workbook_path)),
            sheet_count=len(inventories),
            sheets=inventories
        )

    def validate_sheets(
        self,
        workbook_path,
        sheets: list[dict]
    ) -> WorkbookValidationReport:
        issues = []

        for sheet in sheets:
            issues.extend(
                self._validate_sheet(sheet)
            )

        return WorkbookValidationReport(
            workbook_path=str(Path(workbook_path)),
            issue_count=len(issues),
            issues=issues
        )

    def render_inventory_markdown(
        self,
        inventory: WorkbookInventory
    ) -> str:
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
                    (
                        "- Detected header row: "
                        f"{sheet.header_row_number or 'Not detected'}"
                    ),
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

    def render_validation_markdown(
        self,
        validation: WorkbookValidationReport
    ) -> str:
        lines = [
            "# Workbook Validation",
            "",
            f"**Workbook:** {validation.workbook_path}",
            f"**Issue Count:** {validation.issue_count}",
            "",
        ]

        if not validation.issues:
            lines.append("No validation issues found.")
            return "\n".join(lines).rstrip() + "\n"

        lines.extend(
            [
                "| Sheet | Row | Column | Issue | Value | Message |",
                "|---|---|---|---|---|---|",
            ]
        )

        for issue in validation.issues:
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._escape_markdown_cell(issue.sheet_name),
                        self._escape_markdown_cell(
                            issue.row_number
                            if issue.row_number is not None
                            else ""
                        ),
                        self._escape_markdown_cell(
                            issue.column_name or ""
                        ),
                        self._escape_markdown_cell(issue.issue_type),
                        self._escape_markdown_cell(issue.value or ""),
                        self._escape_markdown_cell(issue.message),
                    ]
                )
                + " |"
            )

        return "\n".join(lines).rstrip() + "\n"

    def write_reports(
        self,
        workbook_path,
        reports_folder="Reports"
    ) -> WorkbookIngestionResult:
        result = self.ingest(workbook_path)
        output_folder = Path(reports_folder)
        output_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        inventory_path = output_folder / "workbook_inventory.md"
        validation_path = output_folder / "workbook_validation.md"

        inventory_path.write_text(
            self.render_inventory_markdown(result.inventory),
            encoding="utf-8"
        )
        validation_path.write_text(
            self.render_validation_markdown(result.validation),
            encoding="utf-8"
        )

        return result

    def _read_workbook(self, workbook_path) -> list[dict]:
        path = self._validate_workbook_path(workbook_path)

        workbook = pd.ExcelFile(
            path,
            engine="openpyxl"
        )

        sheets = []

        for sheet_name in workbook.sheet_names:
            raw_dataframe = pd.read_excel(
                workbook,
                sheet_name=sheet_name,
                header=None,
                dtype=object
            )

            column_names, rows, header_row_number = self._split_header_and_rows(
                raw_dataframe
            )

            sheets.append(
                {
                    "sheet_name": sheet_name,
                    "header_row_number": header_row_number,
                    "column_names": column_names,
                    "rows": rows,
                }
            )

        return sheets

    def _validate_workbook_path(self, workbook_path) -> Path:
        path = Path(workbook_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Workbook file not found: {path}"
            )

        if path.suffix.lower() != ".xlsx":
            raise ValueError(
                f"Workbook ingestion only supports .xlsx files: {path}"
            )

        return path

    def _split_header_and_rows(
        self,
        dataframe
    ) -> tuple[list[str], list[list], int | None]:
        if dataframe.empty:
            return [], [], None

        header_row_index = self._detect_header_row_index(dataframe)

        if header_row_index is None:
            return [], [], None

        header_values = dataframe.iloc[header_row_index].tolist()
        column_names = [
            self._clean_column_name(value)
            for value in header_values
        ]
        rows = dataframe.iloc[header_row_index + 1:].values.tolist()

        return column_names, rows, header_row_index + 1

    def _detect_header_row_index(self, dataframe) -> int | None:
        row_limit = min(
            self.HEADER_SCAN_LIMIT,
            len(dataframe)
        )
        best_row_index = None
        best_score = None

        for row_index in range(row_limit):
            row_values = dataframe.iloc[row_index].tolist()
            non_blank_count = sum(
                not self._is_blank_value(value)
                for value in row_values
            )

            if non_blank_count == 0:
                continue

            keyword_count = self._header_keyword_count(row_values)
            score = (
                keyword_count > 0,
                keyword_count,
                non_blank_count,
                -row_index,
            )

            if best_score is None or score > best_score:
                best_score = score
                best_row_index = row_index

        return best_row_index

    def _header_keyword_count(self, row_values: list) -> int:
        count = 0

        for value in row_values:
            normalized = self._normalize_column_name(
                self._clean_column_name(value)
            )

            if not normalized:
                continue

            if normalized in self.HEADER_KEYWORDS:
                count += 1

        return count

    def _validate_sheet(self, sheet: dict) -> list[WorkbookValidationIssue]:
        sheet_name = sheet["sheet_name"]
        header_row_number = sheet["header_row_number"]
        column_names = sheet["column_names"]
        rows = sheet["rows"]
        issues = []

        if not rows:
            issues.append(
                WorkbookValidationIssue(
                    sheet_name=sheet_name,
                    issue_type="empty_sheet",
                    message="Sheet has no data rows."
                )
            )

        issues.extend(
            self._duplicate_column_issues(
                sheet_name,
                column_names
            )
        )

        column_keys = self._unique_column_keys(column_names)
        first_data_row_number = (
            header_row_number + 1
            if header_row_number is not None
            else 1
        )

        for row_index, row in enumerate(rows, start=first_data_row_number):
            row_values = list(row)

            if self._is_blank_row(row_values):
                issues.append(
                    WorkbookValidationIssue(
                        sheet_name=sheet_name,
                        row_number=row_index,
                        issue_type="blank_row",
                        message="Row is fully blank."
                    )
                )
                continue

            row_map = dict(zip(column_keys, row_values))

            issues.extend(
                self._agent_missing_issues(
                    sheet_name,
                    row_index,
                    column_names,
                    column_keys,
                    row_map
                )
            )
            issues.extend(
                self._numeric_value_issues(
                    sheet_name,
                    row_index,
                    column_names,
                    column_keys,
                    row_map
                )
            )

        return issues

    def _duplicate_column_issues(
        self,
        sheet_name: str,
        column_names: list[str]
    ) -> list[WorkbookValidationIssue]:
        issues = []
        normalized_counts = Counter(
            normalized
            for column_name in column_names
            for normalized in [column_name.strip().lower()]
            if normalized
        )

        for column_name, count in normalized_counts.items():
            if count > 1:
                issues.append(
                    WorkbookValidationIssue(
                        sheet_name=sheet_name,
                        column_name=column_name,
                        issue_type="duplicate_column",
                        message=(
                            f"Column name appears {count} times."
                        )
                    )
                )

        return issues

    def _agent_missing_issues(
        self,
        sheet_name: str,
        row_index: int,
        column_names: list[str],
        column_keys: list[str],
        row_map: dict
    ) -> list[WorkbookValidationIssue]:
        issues = []

        for column_name, column_key in zip(column_names, column_keys):
            normalized = self._normalize_column_name(column_name)

            if (
                normalized in self.AGENT_NAME_COLUMNS
                or normalized in self.AGENT_ID_COLUMNS
            ) and self._is_blank_value(row_map.get(column_key)):
                issues.append(
                    WorkbookValidationIssue(
                        sheet_name=sheet_name,
                        row_number=row_index,
                        column_name=column_name,
                        issue_type="missing_agent_identifier",
                        message=(
                            f"Missing agent name or ID in column "
                            f"'{column_name}'."
                        )
                    )
                )

        return issues

    def _numeric_value_issues(
        self,
        sheet_name: str,
        row_index: int,
        column_names: list[str],
        column_keys: list[str],
        row_map: dict
    ) -> list[WorkbookValidationIssue]:
        issues = []

        for column_name, column_key in zip(column_names, column_keys):
            value = row_map.get(column_key)

            if self._is_blank_value(value):
                continue

            numeric_value = pd.to_numeric(
                value,
                errors="coerce"
            )

            if pd.isna(numeric_value):
                continue

            normalized = self._normalize_column_name(column_name)

            if normalized in self.OSAT_COLUMNS:
                issues.extend(
                    self._osat_issues(
                        sheet_name,
                        row_index,
                        column_name,
                        numeric_value
                    )
                )
            elif normalized in self.CSAT_COLUMNS:
                issues.extend(
                    self._percentage_issues(
                        sheet_name,
                        row_index,
                        column_name,
                        numeric_value,
                        "csat"
                    )
                )
            elif normalized in self.QA_COLUMNS:
                issues.extend(
                    self._percentage_issues(
                        sheet_name,
                        row_index,
                        column_name,
                        numeric_value,
                        "qa"
                    )
                )

        return issues

    def _osat_issues(
        self,
        sheet_name: str,
        row_index: int,
        column_name: str,
        numeric_value
    ) -> list[WorkbookValidationIssue]:
        issues = []

        if numeric_value < 0:
            issues.append(
                self._numeric_issue(
                    sheet_name,
                    row_index,
                    column_name,
                    numeric_value,
                    "negative_numeric_value",
                    "OSAT value is below 0."
                )
            )

        if numeric_value > 10:
            issues.append(
                self._numeric_issue(
                    sheet_name,
                    row_index,
                    column_name,
                    numeric_value,
                    "osat_above_10",
                    "OSAT value is above 10."
                )
            )

        return issues

    def _percentage_issues(
        self,
        sheet_name: str,
        row_index: int,
        column_name: str,
        numeric_value,
        metric_name: str
    ) -> list[WorkbookValidationIssue]:
        issues = []

        if numeric_value < 0:
            issues.append(
                self._numeric_issue(
                    sheet_name,
                    row_index,
                    column_name,
                    numeric_value,
                    "negative_numeric_value",
                    f"{metric_name.upper()} value is below 0."
                )
            )

        if numeric_value > 100:
            issues.append(
                self._numeric_issue(
                    sheet_name,
                    row_index,
                    column_name,
                    numeric_value,
                    f"{metric_name}_above_100",
                    f"{metric_name.upper()} percentage is above 100."
                )
            )

        return issues

    def _numeric_issue(
        self,
        sheet_name: str,
        row_index: int,
        column_name: str,
        numeric_value,
        issue_type: str,
        message: str
    ) -> WorkbookValidationIssue:
        return WorkbookValidationIssue(
            sheet_name=sheet_name,
            row_number=row_index,
            column_name=column_name,
            issue_type=issue_type,
            value=self._clean_cell_value(numeric_value),
            message=message
        )

    def _sample_rows(
        self,
        column_names: list[str],
        rows: list[list]
    ) -> list[dict]:
        column_keys = self._unique_column_keys(column_names)
        sample_rows = []

        for row in rows[:self.SAMPLE_ROW_LIMIT]:
            sample_rows.append(
                {
                    column_key: self._clean_cell_value(value)
                    for column_key, value in zip(column_keys, row)
                }
            )

        return sample_rows

    def _render_sample_rows(
        self,
        column_names: list[str],
        sample_rows: list[dict]
    ) -> list[str]:
        column_keys = self._unique_column_keys(column_names)
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
                    row.get(column_key, "")
                )
                for column_key in column_keys
            ]
            lines.append(
                "| " + " | ".join(values) + " |"
            )

        return lines

    def _unique_column_keys(
        self,
        column_names: list[str]
    ) -> list[str]:
        counts = {}
        keys = []

        for column_name in column_names:
            count = counts.get(column_name, 0) + 1
            counts[column_name] = count

            if count == 1:
                keys.append(column_name)
            else:
                keys.append(f"{column_name} ({count})")

        return keys

    def _clean_column_name(self, value: Any) -> str:
        if self._is_blank_value(value):
            return ""

        return str(value).strip()

    def _normalize_column_name(self, value: str) -> str:
        return " ".join(
            str(value).strip().lower().replace("_", " ").split()
        )

    def _clean_cell_value(self, value: Any) -> str:
        if self._is_blank_value(value):
            return ""

        text = str(value)

        if len(text) > self.CELL_VALUE_LIMIT:
            return text[:self.CELL_VALUE_LIMIT]

        return text

    def _is_blank_row(self, row_values: list) -> bool:
        return all(
            self._is_blank_value(value)
            for value in row_values
        )

    def _is_blank_value(self, value: Any) -> bool:
        if value is None:
            return True

        try:
            if pd.isna(value):
                return True
        except TypeError:
            pass

        return str(value).strip() == ""

    def _escape_markdown_cell(self, value: Any) -> str:
        text = str(value)
        text = text.replace("\r", " ")
        text = text.replace("\n", " ")
        text = text.replace("|", "\\|")
        return text
