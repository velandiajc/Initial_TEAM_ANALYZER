from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.permissions import GovernanceRole
from app.core.tenant_context import TenantContext
from app.models.operational_source import (
    OperationalEntityScope,
    OperationalSourceRecord,
    OperationalSourceType,
    SourceRegistryEntry,
    SourceValidationStatus,
)
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.source_registry_service import SourceRegistryService
from app.services.source_validation_service import SourceValidationService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_operational_source_repository import (
    SQLiteOperationalSourceRepository,
)
from app.services.sqlite_source_registry_repository import (
    SQLiteSourceRegistryRepository,
)
from app.services.sqlite_source_validation_repository import (
    SQLiteSourceValidationRepository,
)


CSV_PATH = Path(
    r"C:\Users\Nuvo CX\Desktop\TEAM_ANALYZER\Data\raw\cxone"
    r"\TEAM_ANALYZER_AHT_PRODUCTIVITY_SOURCE_20260606T152412.CSV"
)
SOURCE_REFERENCE = "cxone:TEAM_ANALYZER_AHT_PRODUCTIVITY_SOURCE_20260606T152412.CSV"
DEMO_DB_PATH = Path("Reports/sprint3_cxone_aht_demo.db")
TENANT_ID = "tenant-demo"
SOURCE_NAME = "CXone AHT Productivity Source"

REQUIRED_FIELD_MAP = {
    "Handled": "handled",
    "Handle Time": "handle_time",
    "Avg Handle Time": "avg_handle_time",
}

OPTIONAL_FIELD_MAP = {
    "Inbound Handled": "inbound_handled",
    "Outbound Handled": "outbound_handled",
    "Agent Contacts": "agent_contacts",
    "Contacts": "contacts",
    "In SLA": "in_sla",
    "Out SLA": "out_sla",
    "Talk Time": "talk_time",
    "Login Time": "login_time",
    "Unavailable Time": "unavailable_time",
    "Inbound Handle Time": "inbound_handle_time",
    "Occupancy": "occupancy",
    "Service Level": "service_level",
    "Avg Hold Time": "avg_hold_time",
    "Avg Talk Time": "avg_talk_time",
    "Hold Time": "hold_time",
    "Avg ACW Time": "avg_acw_time",
}

PERCENT_FIELD_MAP = {
    "% Handle Time": "handle_time_percent",
    "% Talk Time": "talk_time_percent",
    "% Available Time": "available_time_percent",
    "% Unavailable Time": "unavailable_time_percent",
    "% Out SLA": "out_sla_percent",
    "% In SLA": "in_sla_percent",
}


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CXone export not found: {CSV_PATH}")

    if DEMO_DB_PATH.exists():
        DEMO_DB_PATH.unlink()

    database = DatabaseService(DEMO_DB_PATH)
    database.initialize()

    context = TenantContext(
        tenant_id=TENANT_ID,
        user_id="demo-admin",
        roles={GovernanceRole.GOVERNANCE_ADMIN.value},
    )

    source_registry_repository = SQLiteSourceRegistryRepository(database)
    source_repository = SQLiteOperationalSourceRepository(database)
    validation_repository = SQLiteSourceValidationRepository(database)
    audit_service = KPIAuditService(SQLiteKPIAuditRepository(database))

    registry_service = SourceRegistryService(
        source_registry_repository,
        audit_service,
    )
    validation_service = SourceValidationService(
        source_registry_repository,
        source_repository=None,
        validation_repository=None,
        audit_service=None,
    )

    source_type = choose_source_type()
    register_source_type(
        registry_service,
        context,
        source_type,
    )

    rows_loaded = 0
    rows_skipped = 0
    records_created = 0
    valid_records = 0
    invalid_records = 0
    warnings = 0
    created_records: list[OperationalSourceRecord] = []

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row_number, raw_row in enumerate(reader, start=2):
            rows_loaded += 1
            row = clean_row(raw_row)

            if is_grand_total(row) or not row.get("Agent ID", "").strip():
                rows_skipped += 1
                continue

            source_record = build_source_record(
                row,
                row_number,
                source_type,
            )
            result = validation_service.validate_source(
                context,
                source_record,
            )
            records_created += 1

            if result.validation_status == SourceValidationStatus.VALID:
                source_repository.save(
                    context,
                    source_record,
                )
                valid_records += 1
                created_records.append(source_record)
            elif result.validation_status == SourceValidationStatus.WARNING:
                source_repository.save(
                    context,
                    source_record,
                )
                warnings += 1
                created_records.append(source_record)
            else:
                invalid_records += 1

    print_summary(
        rows_loaded=rows_loaded,
        rows_skipped=rows_skipped,
        source_type=source_type,
        records_created=records_created,
        valid_records=valid_records,
        invalid_records=invalid_records,
        warnings=warnings,
        created_records=created_records,
    )


def choose_source_type() -> OperationalSourceType:
    if hasattr(OperationalSourceType, "AHT_RECORD"):
        return OperationalSourceType.AHT_RECORD

    if hasattr(OperationalSourceType, "PRODUCTIVITY_RECORD"):
        return OperationalSourceType.PRODUCTIVITY_RECORD

    return OperationalSourceType.CUSTOM


def register_source_type(
    registry_service: SourceRegistryService,
    context: TenantContext,
    source_type: OperationalSourceType,
) -> None:
    existing = registry_service.registry_repository.get_entry(
        context,
        source_type,
    )

    if existing is not None:
        return

    registry_service.register_source_type(
        context,
        SourceRegistryEntry(
            tenant_id=TENANT_ID,
            source_type=source_type,
            source_name=SOURCE_NAME,
            source_owner="cxone-operations",
            source_steward="workforce-analytics",
            allowed_entity_scopes=[OperationalEntityScope.AGENT],
            required_fields=list(REQUIRED_FIELD_MAP.values()),
            numeric_fields=list(REQUIRED_FIELD_MAP.values())
            + list(OPTIONAL_FIELD_MAP.values())
            + list(PERCENT_FIELD_MAP.values()),
            freshness_threshold_hours=None,
            created_by=context.user_id,
            metadata={
                "source_system": "cxone",
                "demo_only": True,
            },
        ),
    )


def clean_row(raw_row: dict[str, str]) -> dict[str, str]:
    row = {}

    for key, value in raw_row.items():
        if key is None:
            continue

        clean_key = key.strip()

        if not clean_key or clean_key.lower().startswith("unnamed"):
            continue

        row[clean_key] = (value or "").strip()

    return row


def is_grand_total(row: dict[str, str]) -> bool:
    return any(
        value.strip().lower() == "grand total"
        for value in row.values()
        if isinstance(value, str)
    )


def build_source_record(
    row: dict[str, str],
    row_number: int,
    source_type: OperationalSourceType,
) -> OperationalSourceRecord:
    period = datetime.strptime(row["Date"], "%Y/%m/%d")
    agent_id = row["Agent ID"].strip()
    skill_id = row.get("Skill ID", "").strip()
    metric_values = normalize_metric_values(row)
    lineage_parts = [
        period.strftime("%Y%m%d"),
        f"agent-{agent_id}",
    ]

    if skill_id:
        lineage_parts.append(f"skill-{skill_id}")

    return OperationalSourceRecord(
        tenant_id=TENANT_ID,
        source_type=source_type,
        source_reference=SOURCE_REFERENCE,
        source_version="v1",
        lineage_id=":".join(lineage_parts),
        period_start=period,
        period_end=period,
        entity_type=OperationalEntityScope.AGENT,
        entity_id=agent_id,
        source_record_id=f"cxone-aht-{period.strftime('%Y%m%d')}-{agent_id}-{skill_id or row_number}",
        metric_values=metric_values,
        metadata={
            "row_number": row_number,
            "media_type": row.get("Media Type Name", ""),
            "skill_id": skill_id,
            "team_id": row.get("Team ID", ""),
        },
    )


def normalize_metric_values(row: dict[str, str]) -> dict[str, float]:
    values: dict[str, float] = {}

    for csv_field, metric_name in REQUIRED_FIELD_MAP.items():
        values[metric_name] = parse_number(row.get(csv_field, ""))

    for csv_field, metric_name in OPTIONAL_FIELD_MAP.items():
        value = parse_optional_number(row.get(csv_field, ""))

        if value is not None:
            values[metric_name] = value

    for csv_field, metric_name in PERCENT_FIELD_MAP.items():
        value = parse_optional_number(row.get(csv_field, ""))

        if value is not None:
            values[metric_name] = value

    return values


def parse_number(value: str) -> float:
    parsed = parse_optional_number(value)

    if parsed is None:
        return 0.0

    return parsed


def parse_optional_number(value: str) -> float | None:
    clean_value = str(value or "").strip()

    if not clean_value:
        return None

    if clean_value.endswith("%"):
        clean_value = clean_value[:-1]

    clean_value = clean_value.replace(",", "")

    try:
        return float(clean_value)
    except ValueError:
        return None


def print_summary(
    rows_loaded: int,
    rows_skipped: int,
    source_type: OperationalSourceType,
    records_created: int,
    valid_records: int,
    invalid_records: int,
    warnings: int,
    created_records: list[OperationalSourceRecord],
) -> None:
    aht_values = [
        record.metric_values["avg_handle_time"]
        for record in created_records
        if record.metric_values.get("handled", 0) > 0
    ]
    total_handled = sum(
        record.metric_values.get("handled", 0)
        for record in created_records
    )
    by_agent = aggregate_by_agent(created_records)

    print("Sprint 3 CXone AHT/Productivity Demo")
    print(f"CSV path: {CSV_PATH}")
    print(f"Database path: {DEMO_DB_PATH}")
    print(f"Rows loaded: {rows_loaded}")
    print(f"Rows skipped: {rows_skipped}")
    print(f"Source types registered: {source_type.value}")
    print(f"Source records created: {records_created}")
    print(f"Valid records: {valid_records}")
    print(f"Invalid records: {invalid_records}")
    print(f"Warnings: {warnings}")
    print(f"Average AHT seconds: {mean(aht_values):.2f}" if aht_values else "Average AHT seconds: 0.00")
    print(f"Total handled: {total_handled:.0f}")
    print("")
    print("Top 10 agents by handled contacts:")

    for agent_id, metrics in top_by_handled(by_agent)[:10]:
        print(
            f"- {agent_id}: handled={metrics['handled']:.0f}, "
            f"avg_aht_seconds={metrics['avg_handle_time']:.2f}"
        )

    print("")
    print("Top 10 agents by highest AHT among agents with handled > 0:")

    for agent_id, metrics in top_by_aht(by_agent)[:10]:
        print(
            f"- {agent_id}: avg_aht_seconds={metrics['avg_handle_time']:.2f}, "
            f"handled={metrics['handled']:.0f}"
        )


def aggregate_by_agent(
    records: list[OperationalSourceRecord],
) -> dict[str, dict[str, float]]:
    grouped = defaultdict(lambda: {"handled": 0.0, "handle_time": 0.0})

    for record in records:
        grouped[record.entity_id]["handled"] += record.metric_values.get("handled", 0)
        grouped[record.entity_id]["handle_time"] += record.metric_values.get("handle_time", 0)

    for metrics in grouped.values():
        handled = metrics["handled"]
        metrics["avg_handle_time"] = (
            metrics["handle_time"] / handled
            if handled > 0
            else 0.0
        )

    return grouped


def top_by_handled(
    by_agent: dict[str, dict[str, float]],
) -> list[tuple[str, dict[str, float]]]:
    return sorted(
        by_agent.items(),
        key=lambda item: item[1]["handled"],
        reverse=True,
    )


def top_by_aht(
    by_agent: dict[str, dict[str, float]],
) -> list[tuple[str, dict[str, float]]]:
    return sorted(
        (
            item
            for item in by_agent.items()
            if item[1]["handled"] > 0
        ),
        key=lambda item: item[1]["avg_handle_time"],
        reverse=True,
    )


if __name__ == "__main__":
    main()
