from pathlib import Path
from typing import Any

import pandas as pd

from app.models.agent_scorecard import (
    AgentScorecard,
    AgentScorecardReport,
)
from app.services.workbook_entity_discovery_service import (
    WorkbookEntityDiscoveryService,
)
from app.services.workbook_ingestion_service import WorkbookIngestionService
from app.services.pci_redaction_service import PCIRedactionService


class AgentScorecardService:
    DEFAULT_SHEET_NAME = "Roaster"

    FIELD_ALIASES = {
        "agent_name": ["Name", "Agent Name", "Agent"],
        "agent_id": ["ID", "Agent ID", "Employee ID"],
        "email": ["Email", "Agent Email"],
        "supervisor": ["Supervisor", "Supervisor Name"],
        "csat_mtd": ["CSAT MTD", "CSAT", "Avg CSAT"],
        "qa_mtd": ["QA MTD", "QA", "QA Score"],
        "detractors": ["Detractors", "Detractor Count"],
        "open_dsat": ["Open DSAT", "Open Detractors"],
        "risk_level": ["Risk_Final", "Risk Final", "Risk Level"],
        "critical_flag": ["Critical Flag", "Critical"],
        "main_dsat_driver": ["Main DSAT Driver", "DSAT Driver"],
        "qa_main_gap": ["QA Main Gap", "Main QA Gap"],
        "coaching_focus": ["Coaching Focus"],
        "coaching_needed": ["Coaching Needed"],
        "coaching_action": ["Coaching Action (Auto)", "Coaching Action"],
        "coaching_topic": ["Coaching Topic (Auto)", "Coaching Topic"],
        "coaching_reason": ["Coaching Reason (Auto)", "Coaching Reason"],
        "schedule": ["Schedule", "Shift", "Supervisor Schedule"],
    }

    def __init__(
        self,
        workbook_ingestion_service: WorkbookIngestionService | None = None,
        entity_discovery_service: WorkbookEntityDiscoveryService | None = None
    ):
        self.workbook_ingestion_service = (
            workbook_ingestion_service or WorkbookIngestionService()
        )
        self.entity_discovery_service = (
            entity_discovery_service or WorkbookEntityDiscoveryService()
        )
        self.pci_redaction_service = PCIRedactionService()

    def build_report(
        self,
        workbook_path,
        sheet_name: str = DEFAULT_SHEET_NAME
    ) -> AgentScorecardReport:
        sheets = self.workbook_ingestion_service._read_workbook(workbook_path)
        inventory = self.workbook_ingestion_service.build_inventory_from_sheets(
            workbook_path,
            sheets
        )
        entity_report = self.entity_discovery_service.discover(inventory)
        sheet = self._find_sheet(
            sheets,
            sheet_name
        )

        scorecards = self._scorecards_from_sheet(sheet)
        discovered_entities = [
            discovery.entity
            for discovery in entity_report.discoveries
            if self._normalize(discovery.sheet_name) == self._normalize(sheet_name)
        ]

        return AgentScorecardReport(
            workbook_path=str(Path(workbook_path)),
            sheet_name=sheet["sheet_name"],
            scorecards=scorecards,
            discovered_entities=discovered_entities
        )

    def write_report(
        self,
        workbook_path,
        output_path="Reports/Sprint_1_Demos/agent_scorecards.md",
        sheet_name: str = DEFAULT_SHEET_NAME
    ) -> AgentScorecardReport:
        report = self.build_report(
            workbook_path,
            sheet_name
        )
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

    def render_markdown(
        self,
        report: AgentScorecardReport
    ) -> str:
        lines = [
            "# Agent Scorecards",
            "",
            f"**Workbook:** {report.workbook_path}",
            f"**Sheet:** {report.sheet_name}",
            f"**Scorecard Count:** {len(report.scorecards)}",
            (
                "**Discovered Entities:** "
                f"{', '.join(report.discovered_entities) or 'None'}"
            ),
            "",
        ]

        if not report.scorecards:
            lines.append("No agent scorecards generated.")
            return "\n".join(lines).rstrip() + "\n"

        for scorecard in report.scorecards:
            title = scorecard.agent_name or "Unknown Agent"
            lines.extend(
                [
                    f"## {title}",
                    "",
                    "| Field | Value |",
                    "|---|---|",
                ]
            )
            lines.extend(
                self._scorecard_rows(scorecard)
            )
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _find_sheet(
        self,
        sheets: list[dict],
        sheet_name: str
    ) -> dict:
        normalized_name = self._normalize(sheet_name)

        for sheet in sheets:
            if self._normalize(sheet["sheet_name"]) == normalized_name:
                return sheet

        available = ", ".join(
            sheet["sheet_name"]
            for sheet in sheets
        )
        raise ValueError(
            f"Workbook sheet '{sheet_name}' was not found. "
            f"Available sheets: {available}"
        )

    def _scorecards_from_sheet(
        self,
        sheet: dict
    ) -> list[AgentScorecard]:
        column_lookup = self._column_lookup(sheet["column_names"])
        scorecards = []

        for row in sheet["rows"]:
            if self._is_blank_row(row):
                continue

            row_values = self._row_values(
                sheet["column_names"],
                row
            )

            scorecard = AgentScorecard(
                agent_name=self._value(row_values, column_lookup, "agent_name"),
                agent_id=self._value(row_values, column_lookup, "agent_id"),
                email=self._value(row_values, column_lookup, "email"),
                supervisor=self._value(row_values, column_lookup, "supervisor"),
                csat_mtd=self._value(row_values, column_lookup, "csat_mtd"),
                qa_mtd=self._value(row_values, column_lookup, "qa_mtd"),
                detractors=self._value(row_values, column_lookup, "detractors"),
                open_dsat=self._value(row_values, column_lookup, "open_dsat"),
                risk_level=self._value(row_values, column_lookup, "risk_level"),
                critical_flag=self._value(row_values, column_lookup, "critical_flag"),
                main_dsat_driver=self._value(
                    row_values,
                    column_lookup,
                    "main_dsat_driver"
                ),
                qa_main_gap=self._value(row_values, column_lookup, "qa_main_gap"),
                coaching_focus=self._value(
                    row_values,
                    column_lookup,
                    "coaching_focus"
                ),
                coaching_needed=self._value(
                    row_values,
                    column_lookup,
                    "coaching_needed"
                ),
                coaching_action=self._value(
                    row_values,
                    column_lookup,
                    "coaching_action"
                ),
                coaching_topic=self._value(
                    row_values,
                    column_lookup,
                    "coaching_topic"
                ),
                coaching_reason=self._value(
                    row_values,
                    column_lookup,
                    "coaching_reason"
                ),
                schedule=self._value(row_values, column_lookup, "schedule"),
                supervisor_recommendation="",
            )
            scorecard.supervisor_recommendation = (
                self._supervisor_recommendation(scorecard)
            )
            scorecards.append(scorecard)

        return scorecards

    def _column_lookup(
        self,
        column_names: list[str]
    ) -> dict[str, str]:
        normalized_columns = {
            self._normalize(column_name): column_name
            for column_name in column_names
            if self._normalize(column_name)
        }
        lookup = {}

        for field_name, aliases in self.FIELD_ALIASES.items():
            for alias in aliases:
                normalized_alias = self._normalize(alias)

                if normalized_alias in normalized_columns:
                    lookup[field_name] = normalized_columns[normalized_alias]
                    break

        return lookup

    def _row_values(
        self,
        column_names: list[str],
        row: list
    ) -> dict[str, Any]:
        return {
            column_name: value
            for column_name, value in zip(column_names, row)
        }

    def _value(
        self,
        row_values: dict[str, Any],
        column_lookup: dict[str, str],
        field_name: str
    ) -> str:
        column_name = column_lookup.get(field_name)

        if column_name is None:
            return ""

        return self._clean_value(
            row_values.get(column_name),
            field_name
        )

    def _supervisor_recommendation(
        self,
        scorecard: AgentScorecard
    ) -> str:
        risk_level = self._display_value(scorecard.risk_level)
        critical_flag = self._display_value(scorecard.critical_flag)
        dsat_driver = self._display_value(scorecard.main_dsat_driver)
        qa_gap = self._display_value(scorecard.qa_main_gap)
        coaching_action = self._display_value(scorecard.coaching_action)
        coaching_reason = self._display_value(scorecard.coaching_reason)
        open_dsat = self._display_value(scorecard.open_dsat)
        detractors = self._display_value(scorecard.detractors)
        normalized_risk = self._normalize(scorecard.risk_level)
        exposure = (
            f"{open_dsat} open DSAT and {detractors} detractors"
        )

        if self._is_affirmative(scorecard.critical_flag):
            return (
                "Schedule immediate supervisor follow-up. "
                f"Risk level: {risk_level}. Critical flag: {critical_flag}. "
                f"Prioritize DSAT driver '{dsat_driver}' and QA gap "
                f"'{qa_gap}'. Execute coaching action: {coaching_action}. "
                f"Reason: {coaching_reason}. Current exposure: {exposure}."
            )

        if normalized_risk in {
            "high",
            "critical",
            "red",
        }:
            return (
                "Prioritize a risk review this week. "
                f"Risk level: {risk_level}. Focus coaching on DSAT driver "
                f"'{dsat_driver}' and QA gap '{qa_gap}'. Use action "
                f"'{coaching_action}' because {coaching_reason}. "
                f"Monitor exposure: {exposure}."
            )

        if normalized_risk in {
            "medium",
            "moderate",
            "yellow",
        }:
            return (
                "Schedule targeted coaching in the next supervisor 1:1. "
                f"Risk level: {risk_level}. Review DSAT driver "
                f"'{dsat_driver}', QA gap '{qa_gap}', and action "
                f"'{coaching_action}'. Track {exposure} for movement."
            )

        if self._positive_number(scorecard.open_dsat) or self._positive_number(
            scorecard.detractors
        ):
            return (
                "Review customer experience exposure before the next shift. "
                f"Current exposure: {exposure}. Coach against DSAT driver "
                f"'{dsat_driver}' and QA gap '{qa_gap}'."
            )

        if self._is_affirmative(scorecard.coaching_needed):
            return (
                "Complete the planned coaching action and confirm behavior "
                "change in the next supervisor check-in."
            )

        return (
            "Maintain current performance rhythm and monitor CSAT, QA, and "
            "schedule adherence in the next review."
        )

    def _scorecard_rows(
        self,
        scorecard: AgentScorecard
    ) -> list[str]:
        fields = [
            ("Agent name", scorecard.agent_name),
            ("ID", scorecard.agent_id),
            ("Email", scorecard.email),
            ("Supervisor", scorecard.supervisor),
            ("CSAT MTD", scorecard.csat_mtd),
            ("QA MTD", scorecard.qa_mtd),
            ("Detractors", scorecard.detractors),
            ("Open DSAT", scorecard.open_dsat),
            ("Risk level", scorecard.risk_level),
            ("Critical flag", scorecard.critical_flag),
            ("Main DSAT driver", scorecard.main_dsat_driver),
            ("QA main gap", scorecard.qa_main_gap),
            ("Coaching focus", scorecard.coaching_focus),
            ("Coaching needed", scorecard.coaching_needed),
            ("Coaching action", scorecard.coaching_action),
            ("Coaching topic", scorecard.coaching_topic),
            ("Coaching reason", scorecard.coaching_reason),
            ("Schedule", scorecard.schedule),
            (
                "Supervisor recommendation",
                scorecard.supervisor_recommendation
            ),
        ]

        return [
            "| "
            + " | ".join(
                [
                    self._escape_markdown_cell(label),
                    self._escape_markdown_cell(value or "Not available"),
                ]
            )
            + " |"
            for label, value in fields
        ]

    def _clean_value(self, value: Any, field_name: str | None = None) -> str:
        if self._is_blank_value(value):
            return ""

        if isinstance(value, float) and value.is_integer():
            text = str(int(value))
        else:
            text = str(value).strip()

        text = self.pci_redaction_service.redact(
            self._clean_mojibake(text)
        )

        if field_name in {
            "csat_mtd",
            "qa_mtd",
        }:
            return self._format_percentage(text)

        return text

    def _format_percentage(self, value: str) -> str:
        text = value.strip()

        if not text:
            return ""

        numeric_text = text.replace("%", "").replace(",", "")

        try:
            numeric_value = float(numeric_text)
        except ValueError:
            return text

        if 0 <= numeric_value <= 1:
            numeric_value *= 100

        return f"{numeric_value:.2f}%"

    def _clean_mojibake(self, value: str) -> str:
        text = value

        if self._looks_like_mojibake(text):
            for encoding in [
                "latin1",
                "cp1252",
            ]:
                try:
                    text = text.encode(encoding).decode("utf-8")
                    break
                except UnicodeError:
                    pass

        replacements = {
            "\U0001f525": "high urgency",
        }

        for bad_text, replacement in replacements.items():
            text = text.replace(bad_text, replacement)

        return " ".join(text.split())

    def _looks_like_mojibake(self, value: str) -> bool:
        markers = [
            "\u00c3",
            "\u00c2",
            "\u00e2\u20ac",
            "\u00f0\u0178",
        ]

        return any(
            marker in value
            for marker in markers
        )

    def _display_value(self, value: str) -> str:
        return value if value else "not available"

    def _is_blank_row(self, row: list) -> bool:
        return all(
            self._is_blank_value(value)
            for value in row
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

    def _positive_number(self, value: str) -> bool:
        try:
            return float(value) > 0
        except (TypeError, ValueError):
            return False

    def _is_affirmative(self, value: str) -> bool:
        return self._normalize(value) in {
            "1",
            "true",
            "yes",
            "y",
            "needed",
            "critical",
        }

    def _normalize(self, value: str) -> str:
        text = str(value).replace("_", " ").replace("-", " ")
        text = text.replace("(", " ").replace(")", " ")
        return " ".join(text.strip().lower().split())

    def _escape_markdown_cell(self, value: Any) -> str:
        text = str(value)
        text = text.replace("\r", " ")
        text = text.replace("\n", " ")
        text = text.replace("|", "\\|")
        return text
