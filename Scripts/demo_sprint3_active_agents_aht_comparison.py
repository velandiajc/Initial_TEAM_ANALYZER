from __future__ import annotations

import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


TEAM_WORKBOOK_PATH = Path(
    r"C:\Users\Nuvo CX\Desktop\TEAM_ANALYZER\Data\raw\workbooks"
    r"\Team JV - MAY.xlsx"
)
CXONE_CSV_PATH = Path(
    r"C:\Users\Nuvo CX\Desktop\TEAM_ANALYZER\Data\raw\cxone"
    r"\TEAM_ANALYZER_AHT_PRODUCTIVITY_SOURCE_20260606T152412.CSV"
)
CSV_REPORT_PATH = Path("Reports/active_agents_aht_comparison.csv")
MARKDOWN_REPORT_PATH = Path("Reports/active_agents_aht_comparison.md")

ROSTER_SHEET_PREFERENCES = [
    "Roaster",
    "Roster",
    "Control Panel",
]
ACTIVE_VALUES = {
    "active",
    "act",
    "yes",
    "y",
    "true",
}
AHT_CATEGORIES = [
    ("Low", 0, 359.9999),
    ("Target", 360, 600),
    ("Elevated", 601, 900),
    ("High", 900.0001, float("inf")),
]


@dataclass
class ActiveAgent:
    name: str
    agent_id: str
    normalized_name: str
    status: str


@dataclass
class AgentAHTResult:
    agent_name: str
    agent_id: str
    match_method: str
    total_handled: float
    total_handle_time: float
    avg_aht_seconds: float | None
    avg_aht_minutes: float | None
    total_talk_time: float
    total_hold_time: float
    avg_acw_time: float | None
    occupancy: float | None
    service_level: float | None
    category: str
    matched_rows: int


def main() -> None:
    require_input_files()
    CSV_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    roster_sheet_name, active_agents, active_assumption = load_active_agents()
    cxone_rows = load_cxone_rows()
    results = compare_active_agents(
        active_agents,
        cxone_rows,
    )

    write_csv_report(results)
    write_markdown_report(
        roster_sheet_name,
        active_agents,
        active_assumption,
        cxone_rows,
        results,
    )
    print_summary(
        roster_sheet_name,
        active_agents,
        results,
    )


def require_input_files() -> None:
    missing = [
        path
        for path in [
            TEAM_WORKBOOK_PATH,
            CXONE_CSV_PATH,
        ]
        if not path.exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required input file(s): "
            + ", ".join(str(path) for path in missing)
        )


def load_active_agents() -> tuple[str, list[ActiveAgent], str]:
    excel = pd.ExcelFile(TEAM_WORKBOOK_PATH)
    sheet_order = ordered_sheet_names(excel.sheet_names)

    for sheet_name in sheet_order:
        table = read_sheet_as_table(sheet_name)

        if table is None:
            continue

        name_column = find_column(
            table.columns,
            ["agent name", "agent", "name"],
        )

        if name_column is None:
            continue

        status_column = find_column(
            table.columns,
            ["active", "status", "employee status", "agent status"],
        )
        id_column = find_column(
            table.columns,
            ["agent id", "id", "agent no", "agentno", "employee id"],
        )
        agents, assumption = active_agents_from_table(
            table,
            name_column,
            id_column,
            status_column,
        )

        if agents:
            return sheet_name, agents, assumption

    raise ValueError("No roster-like sheet with agent names was found.")


def ordered_sheet_names(sheet_names: list[str]) -> list[str]:
    ordered = []

    for preferred in ROSTER_SHEET_PREFERENCES:
        for sheet_name in sheet_names:
            if sheet_name.strip().lower() == preferred.lower():
                ordered.append(sheet_name)

    for sheet_name in sheet_names:
        if sheet_name not in ordered:
            ordered.append(sheet_name)

    return ordered


def read_sheet_as_table(sheet_name: str) -> pd.DataFrame | None:
    raw = pd.read_excel(
        TEAM_WORKBOOK_PATH,
        sheet_name=sheet_name,
        header=None,
    )

    for row_index in range(min(40, len(raw))):
        values = [
            str(value).strip().lower()
            for value in raw.iloc[row_index].tolist()
            if not pd.isna(value) and str(value).strip()
        ]

        has_name = any(value in {"name", "agent", "agent name"} for value in values)
        has_status = any("status" in value or value == "active" for value in values)

        if has_name and has_status:
            header = [
                str(value).strip()
                if not pd.isna(value) and str(value).strip()
                else f"column_{index}"
                for index, value in enumerate(raw.iloc[row_index].tolist())
            ]
            table = raw.iloc[row_index + 1:].copy()
            table.columns = header
            table = table.dropna(how="all")
            return table

    return None


def find_column(
    columns,
    candidates: list[str],
) -> str | None:
    normalized = {
        normalize_header(column): column
        for column in columns
    }

    for candidate in candidates:
        if normalize_header(candidate) in normalized:
            return normalized[normalize_header(candidate)]

    for normalized_column, original in normalized.items():
        if any(normalize_header(candidate) in normalized_column for candidate in candidates):
            return original

    return None


def active_agents_from_table(
    table: pd.DataFrame,
    name_column: str,
    id_column: str | None,
    status_column: str | None,
) -> tuple[list[ActiveAgent], str]:
    agents: list[ActiveAgent] = []
    assumption = "Explicit active/status column used."

    if status_column is None:
        assumption = "No active/status column found; all roster agents were used."

    for _, row in table.iterrows():
        name = clean_text(row.get(name_column, ""))

        if not name or is_summary_label(name):
            continue

        status = clean_text(row.get(status_column, "")) if status_column else "Assumed Active"

        if status_column and status.strip().lower() not in ACTIVE_VALUES:
            continue

        agent_id = clean_identifier(row.get(id_column, "")) if id_column else ""
        agents.append(
            ActiveAgent(
                name=name,
                agent_id=agent_id,
                normalized_name=normalize_name(name),
                status=status,
            )
        )

    deduped = dedupe_agents(agents)

    return deduped, assumption


def load_cxone_rows() -> list[dict[str, Any]]:
    rows = []

    with CXONE_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for raw_row in reader:
            row = clean_row(raw_row)

            if is_grand_total(row):
                continue

            agent_id = clean_identifier(row.get("Agent ID", ""))
            agent_name = clean_text(row.get("Agent Name", ""))

            if not agent_id and not agent_name:
                continue

            row["_agent_id"] = agent_id
            row["_normalized_agent_name"] = normalize_name(agent_name)
            rows.append(row)

    return rows


def compare_active_agents(
    active_agents: list[ActiveAgent],
    cxone_rows: list[dict[str, Any]],
) -> list[AgentAHTResult]:
    rows_by_id: dict[str, list[dict[str, Any]]] = {}
    rows_by_name: dict[str, list[dict[str, Any]]] = {}

    for row in cxone_rows:
        if row["_agent_id"]:
            rows_by_id.setdefault(row["_agent_id"], []).append(row)

        if row["_normalized_agent_name"]:
            rows_by_name.setdefault(row["_normalized_agent_name"], []).append(row)

    results = []

    for agent in active_agents:
        matched_rows = []
        match_method = "No Data"

        if agent.agent_id and agent.agent_id in rows_by_id:
            matched_rows = rows_by_id[agent.agent_id]
            match_method = "Agent ID"
        elif agent.normalized_name in rows_by_name:
            matched_rows = rows_by_name[agent.normalized_name]
            match_method = "Normalized Agent Name"

        results.append(
            calculate_agent_result(
                agent,
                matched_rows,
                match_method,
            )
        )

    return results


def calculate_agent_result(
    agent: ActiveAgent,
    rows: list[dict[str, Any]],
    match_method: str,
) -> AgentAHTResult:
    total_handled = sum(parse_number(row.get("Handled", "")) or 0 for row in rows)
    total_handle_time = sum(parse_number(row.get("Handle Time", "")) or 0 for row in rows)
    total_talk_time = sum(parse_number(row.get("Talk Time", "")) or 0 for row in rows)
    total_hold_time = sum(parse_number(row.get("Hold Time", "")) or 0 for row in rows)
    avg_acw_time = average_metric(rows, "Avg ACW Time")
    occupancy = average_metric(rows, "Occupancy")
    service_level = average_metric(rows, "Service Level")
    avg_handle_time_fallback = average_metric(rows, "Avg Handle Time")
    avg_aht_seconds = None

    if total_handled > 0 and total_handle_time > 0:
        avg_aht_seconds = total_handle_time / total_handled
    elif avg_handle_time_fallback is not None:
        avg_aht_seconds = avg_handle_time_fallback

    avg_aht_minutes = avg_aht_seconds / 60 if avg_aht_seconds is not None else None

    return AgentAHTResult(
        agent_name=agent.name,
        agent_id=agent.agent_id,
        match_method=match_method,
        total_handled=total_handled,
        total_handle_time=total_handle_time,
        avg_aht_seconds=avg_aht_seconds,
        avg_aht_minutes=avg_aht_minutes,
        total_talk_time=total_talk_time,
        total_hold_time=total_hold_time,
        avg_acw_time=avg_acw_time,
        occupancy=occupancy,
        service_level=service_level,
        category=categorize_aht(avg_aht_seconds, total_handled),
        matched_rows=len(rows),
    )


def write_csv_report(results: list[AgentAHTResult]) -> None:
    fieldnames = [
        "agent_name",
        "agent_id",
        "match_method",
        "total_handled",
        "total_handle_time",
        "avg_aht_seconds",
        "avg_aht_minutes",
        "total_talk_time",
        "total_hold_time",
        "avg_acw_time",
        "occupancy",
        "service_level",
        "category",
        "matched_rows",
    ]

    with CSV_REPORT_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            writer.writerow({
                "agent_name": result.agent_name,
                "agent_id": result.agent_id,
                "match_method": result.match_method,
                "total_handled": round(result.total_handled, 2),
                "total_handle_time": round(result.total_handle_time, 2),
                "avg_aht_seconds": format_optional(result.avg_aht_seconds),
                "avg_aht_minutes": format_optional(result.avg_aht_minutes),
                "total_talk_time": round(result.total_talk_time, 2),
                "total_hold_time": round(result.total_hold_time, 2),
                "avg_acw_time": format_optional(result.avg_acw_time),
                "occupancy": format_optional(result.occupancy),
                "service_level": format_optional(result.service_level),
                "category": result.category,
                "matched_rows": result.matched_rows,
            })


def write_markdown_report(
    roster_sheet_name: str,
    active_agents: list[ActiveAgent],
    active_assumption: str,
    cxone_rows: list[dict[str, Any]],
    results: list[AgentAHTResult],
) -> None:
    matched = matched_results(results)
    missing = missing_results(results)
    team_aht = weighted_team_aht(matched)
    category_counts = count_categories(results)
    highest = highest_aht(matched)[:10]
    lowest = lowest_aht(matched)[:10]

    lines = [
        "# Sprint 3 Active-Agent AHT Comparison Demo",
        "",
        "## Executive Summary",
        "",
        f"- Active agents detected: {len(active_agents)}",
        f"- Matched to CXone: {len(matched)}",
        f"- Missing CXone data: {len(missing)}",
        f"- Team average AHT: {format_seconds(team_aht)}",
        f"- Total handled contacts: {sum(result.total_handled for result in matched):.0f}",
        "",
        "## Data Sources Used",
        "",
        f"- Team workbook: `{TEAM_WORKBOOK_PATH}`",
        f"- Roster sheet selected: `{roster_sheet_name}`",
        f"- CXone export: `{CXONE_CSV_PATH}`",
        "",
        "## Matching Method",
        "",
        "- Agent ID was attempted first when available.",
        "- Normalized Agent Name was used as fallback.",
        f"- Active detection note: {active_assumption}",
        "",
        "## Active Agent Coverage",
        "",
        f"- CXone rows considered after filters: {len(cxone_rows)}",
        f"- Coverage: {len(matched)} of {len(active_agents)} active agents matched.",
        "",
        "## Team AHT Summary",
        "",
        f"- Low: {category_counts.get('Low', 0)}",
        f"- Target: {category_counts.get('Target', 0)}",
        f"- Elevated: {category_counts.get('Elevated', 0)}",
        f"- High: {category_counts.get('High', 0)}",
        f"- No Data: {category_counts.get('No Data', 0)}",
        "",
        "## Active Agent AHT Table",
        "",
        "| Agent | Agent ID | Match | Handled | Avg AHT Seconds | Avg AHT Minutes | Category |",
        "|---|---:|---|---:|---:|---:|---|",
    ]

    for result in sorted(results, key=lambda item: item.agent_name):
        lines.append(
            "| "
            f"{result.agent_name} | {result.agent_id or ''} | {result.match_method} | "
            f"{result.total_handled:.0f} | {format_optional(result.avg_aht_seconds)} | "
            f"{format_optional(result.avg_aht_minutes)} | {result.category} |"
        )

    lines.extend([
        "",
        "## Highest AHT Agents",
        "",
    ])
    lines.extend(agent_bullets(highest))
    lines.extend([
        "",
        "## Lowest AHT Agents",
        "",
    ])
    lines.extend(agent_bullets(lowest))
    lines.extend([
        "",
        "## Agents Missing CXone Data",
        "",
    ])

    if missing:
        for result in missing:
            lines.append(f"- {result.agent_name} ({result.agent_id or 'no roster ID'})")
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Data Quality Notes",
        "",
        "- Blank `Unnamed` CXone columns were ignored.",
        "- Grand Total rows were excluded.",
        "- CXone rows without Agent ID and Agent Name were excluded.",
        "- AHT uses weighted Handle Time / Handled when possible.",
        "- Avg Handle Time average is used only when weighted AHT inputs are missing.",
        "- No raw customer comments were read or included.",
        "",
        "## Recommended Next Actions",
        "",
        "- Review High and Elevated AHT agents for operational context before coaching decisions.",
        "- Confirm roster IDs against CXone IDs to improve ID-first matching.",
        "- Validate whether one-contact High AHT outliers should be excluded from leadership summaries.",
    ])

    MARKDOWN_REPORT_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def print_summary(
    roster_sheet_name: str,
    active_agents: list[ActiveAgent],
    results: list[AgentAHTResult],
) -> None:
    matched = matched_results(results)
    missing = missing_results(results)
    highest = highest_aht(matched)[:10]
    team_aht = weighted_team_aht(matched)

    print("Sprint 3 Active-Agent AHT Comparison Demo")
    print(f"Roster sheet selected: {roster_sheet_name}")
    print(f"Active agents detected: {len(active_agents)}")
    print(f"Matched to CXone: {len(matched)}")
    print(f"Missing CXone data: {len(missing)}")
    print(f"Team average AHT seconds: {format_optional(team_aht)}")
    print(f"CSV report: {CSV_REPORT_PATH}")
    print(f"Markdown report: {MARKDOWN_REPORT_PATH}")
    print("")
    print("Highest AHT agents:")

    for result in highest:
        print(
            f"- {result.agent_name}: {format_optional(result.avg_aht_seconds)} seconds, "
            f"handled={result.total_handled:.0f}, category={result.category}"
        )


def clean_row(raw_row: dict[str, Any]) -> dict[str, str]:
    row = {}

    for key, value in raw_row.items():
        if key is None:
            continue

        clean_key = str(key).strip()

        if not clean_key or clean_key.lower().startswith("unnamed"):
            continue

        row[clean_key] = clean_text(value)

    return row


def is_grand_total(row: dict[str, str]) -> bool:
    return any(
        value.strip().lower() == "grand total"
        for value in row.values()
        if isinstance(value, str)
    )


def parse_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    if text.endswith("%"):
        text = text[:-1]

    text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def average_metric(
    rows: list[dict[str, Any]],
    field_name: str,
) -> float | None:
    values = [
        parsed
        for row in rows
        if (parsed := parse_number(row.get(field_name, ""))) is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def categorize_aht(
    avg_aht_seconds: float | None,
    total_handled: float,
) -> str:
    if avg_aht_seconds is None or total_handled <= 0:
        return "No Data"

    for label, minimum, maximum in AHT_CATEGORIES:
        if minimum <= avg_aht_seconds <= maximum:
            return label

    return "No Data"


def matched_results(results: list[AgentAHTResult]) -> list[AgentAHTResult]:
    return [
        result
        for result in results
        if result.category != "No Data"
    ]


def missing_results(results: list[AgentAHTResult]) -> list[AgentAHTResult]:
    return [
        result
        for result in results
        if result.category == "No Data"
    ]


def weighted_team_aht(results: list[AgentAHTResult]) -> float | None:
    handled = sum(result.total_handled for result in results)
    handle_time = sum(result.total_handle_time for result in results)

    if handled > 0 and handle_time > 0:
        return handle_time / handled

    values = [
        result.avg_aht_seconds
        for result in results
        if result.avg_aht_seconds is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def highest_aht(results: list[AgentAHTResult]) -> list[AgentAHTResult]:
    return sorted(
        [
            result
            for result in results
            if result.avg_aht_seconds is not None
        ],
        key=lambda item: item.avg_aht_seconds or 0,
        reverse=True,
    )


def lowest_aht(results: list[AgentAHTResult]) -> list[AgentAHTResult]:
    return sorted(
        [
            result
            for result in results
            if result.avg_aht_seconds is not None
        ],
        key=lambda item: item.avg_aht_seconds or 0,
    )


def count_categories(results: list[AgentAHTResult]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for result in results:
        counts[result.category] = counts.get(result.category, 0) + 1

    return counts


def agent_bullets(results: list[AgentAHTResult]) -> list[str]:
    if not results:
        return ["- None."]

    return [
        (
            f"- {result.agent_name}: {format_optional(result.avg_aht_seconds)} seconds, "
            f"handled={result.total_handled:.0f}, category={result.category}"
        )
        for result in results
    ]


def normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def normalize_name(value: Any) -> str:
    text = clean_text(value)

    if "," in text:
        parts = [
            part.strip()
            for part in text.split(",", 1)
        ]
        text = f"{parts[1]} {parts[0]}"

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()

    return " ".join(text.split())


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return str(value).strip()


def clean_identifier(value: Any) -> str:
    text = clean_text(value)

    if not text:
        return ""

    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]

    return text


def is_summary_label(value: str) -> bool:
    return value.strip().lower() in {
        "total",
        "total agents",
        "high risk",
        "moderate risk",
        "low risk",
        "avg csat",
        "avg qa",
        "open dsat",
    }


def dedupe_agents(agents: list[ActiveAgent]) -> list[ActiveAgent]:
    seen = set()
    deduped = []

    for agent in agents:
        key = agent.agent_id or agent.normalized_name

        if key in seen:
            continue

        seen.add(key)
        deduped.append(agent)

    return deduped


def format_optional(value: float | None) -> str:
    if value is None:
        return ""

    return f"{value:.2f}"


def format_seconds(value: float | None) -> str:
    if value is None:
        return "No Data"

    return f"{value:.2f} seconds"


if __name__ == "__main__":
    main()
