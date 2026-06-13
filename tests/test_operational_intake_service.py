import sqlite3

import pandas as pd
import pytest

from app.core.permissions import (
    GovernanceRole,
    OperationalIntakePermission,
    RBACService,
)
from app.core.tenant_context import TenantContext
from app.services.database_service import DatabaseService
from app.services.kpi_audit_service import KPIAuditService
from app.services.operational_intake_service import OperationalIntakeService
from app.services.sqlite_kpi_audit_repository import SQLiteKPIAuditRepository
from app.services.sqlite_operational_intake_repository import (
    SQLiteOperationalIntakeRepository,
)


def context(tenant_id="tenant-1", roles=None):
    return TenantContext(
        tenant_id=tenant_id,
        user_id="supervisor-1",
        roles=roles or {GovernanceRole.PERFORMANCE_MANAGER.value},
    )


def create_service(tmp_path):
    database = DatabaseService(tmp_path / "intake.db")
    database.initialize()
    audit_service = KPIAuditService(SQLiteKPIAuditRepository(database))
    repository = SQLiteOperationalIntakeRepository(database, audit_service)
    service = OperationalIntakeService(repository, audit_service)
    return database, audit_service, repository, service


def write_csat_export(tmp_path):
    source = tmp_path / "csat_export.csv"
    source.write_text(
        "\n".join([
            "contactid,agentno,agentname,OSAT,Date of Survey,brand,"
            "media_type_name,Driver_Tag,Sub_Driver,"
            "CSAT Category (Auto),disposition_name,OSAT Score Comment",
            "C-1,A-1,Agent One,4,2026-06-01,Brand A,Voice,"
            "Agent Behavior,Empathy,DSAT,Unresolved,Raw customer comment",
            "C-2,A-2,Agent Two,6,2026-06-01,Brand A,Voice,"
            "Process,Refund Delay,DSAT,Unresolved,Another raw customer comment",
            "C-3,A-3,Agent Three,5,2026-06-01,Brand A,Voice,"
            "Agent Behavior,Empathy,DSAT,Resolved,Third raw customer comment",
            "C-4,A-4,Agent Four,9,2026-06-01,Brand A,Voice,"
            "Process,Refund Delay,Promoter,Resolved,Promoter comment",
        ]),
        encoding="utf-8",
    )
    return source


def test_operational_intake_permission_grants_expected_roles():
    rbac = RBACService()

    assert rbac.can(
        context(roles={GovernanceRole.PERFORMANCE_MANAGER.value}),
        OperationalIntakePermission.RUN_OPERATIONAL_INTAKE,
    )
    assert rbac.can(
        context(roles={GovernanceRole.LEADERSHIP.value}),
        OperationalIntakePermission.VIEW_OPERATIONAL_INTAKE,
    )
    assert not rbac.can(
        context(roles={GovernanceRole.LEADERSHIP.value}),
        OperationalIntakePermission.RUN_OPERATIONAL_INTAKE,
    )


def test_operational_intake_classifies_and_ranks_priorities(tmp_path):
    _, _, repository, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)

    run, report = service.run_from_file(
        context(),
        source,
        tmp_path / "Reports",
    )

    assert run.total_records == 4
    assert run.detractor_count == 3
    assert [record.classification for record in run.records] == [
        "Detractor",
        "Detractor",
        "Detractor",
        "Promoter",
    ]
    assert [(row.driver, row.detractor_count) for row in run.priorities] == [
        ("Agent Behavior", 2),
        ("Process", 1),
    ]
    assert run.priorities[0].priority_rank == 1
    assert run.priorities[0].impact_score == 11.0
    assert run.priorities[1].impact_rank == 2
    assert "Detractor Count: 3" in report.content
    assert "Agent Behavior | Detractors: 2" in report.content
    assert "Classification Match Count: 4" in report.content
    assert "Driver Match Count: 4" in report.content
    assert "Sub-Driver Match Count: 4" in report.content
    assert "CSAT Category Match Count: 4" in report.content

    saved_run = repository.get_run(context(), run.run_id)
    saved_report = repository.get_report(context(), run.run_id)

    assert saved_run.detractor_count == 3
    assert saved_report.content == report.content


def test_operational_intake_projection_excludes_comments(tmp_path):
    database, _, repository, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)

    run, _ = service.run_from_file(
        context(),
        source,
        tmp_path / "Reports",
    )

    saved_records = repository.list_records(context(), run.run_id)

    assert saved_records[0].driver == "Agent Behavior"
    assert saved_records[0].sub_driver == "Empathy"
    assert saved_records[0].csat_category == "DSAT"
    with database.connect() as connection:
        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(operational_intake_records)"
            ).fetchall()
        ]
        persisted_text = " ".join(
            str(row)
            for row in connection.execute(
                """
                SELECT contact_id, agent_id, agent_name, driver, sub_driver,
                       csat_category
                FROM operational_intake_records
                WHERE tenant_id = ?
                """,
                (context().tenant_id,),
            ).fetchall()
        )

    assert "comment" not in columns
    assert "Raw customer comment" not in persisted_text


def test_operational_intake_history_is_immutable(tmp_path):
    database, _, _, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)
    run, _ = service.run_from_file(
        context(),
        source,
        tmp_path / "Reports",
    )

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        with database.connect() as connection:
            connection.execute(
                """
                UPDATE operational_intake_runs
                SET detractor_count = 0
                WHERE tenant_id = ? AND run_id = ?
                """,
                (context().tenant_id, run.run_id),
            )


def test_excel_sheet_discovery_selects_valid_csat_sheet(tmp_path):
    _, _, _, service = create_service(tmp_path)
    source = tmp_path / "workbook.xlsx"
    control_panel = pd.DataFrame({
        "Metric": ["Not CSAT"],
        "Value": [1],
    })
    raw_data = pd.DataFrame({
        "contactid": ["X-1"],
        "OSAT": [4],
        "Agent Clean": ["Agent Clean Name"],
        "Driver_Tag": ["Agent Behavior"],
        "Sub_Driver": ["Empathy"],
        "CSAT Category (Auto)": ["DSAT"],
    })
    with pd.ExcelWriter(source) as writer:
        control_panel.to_excel(writer, sheet_name="Control Panel", index=False)
        raw_data.to_excel(writer, sheet_name="MTD CSAT (raw data)", index=False)

    run, report = service.run_from_file(
        context(),
        source,
        tmp_path / "Reports",
    )

    assert run.total_records == 1
    assert run.records[0].agent_name == "Agent Clean Name"
    assert run.metadata["selected_sheet"] == "MTD CSAT (raw data)"
    assert "Selected Sheet: MTD CSAT (raw data)" in report.content


def test_invalid_excel_without_csat_sheet_fails_clearly(tmp_path):
    _, _, _, service = create_service(tmp_path)
    source = tmp_path / "invalid.xlsx"
    pd.DataFrame({
        "Metric": ["Not CSAT"],
        "Value": [1],
    }).to_excel(source, sheet_name="Control Panel", index=False)

    with pytest.raises(ValueError, match="No valid CSAT intake sheet found"):
        service.run_from_file(
            context(),
            source,
            tmp_path / "Reports",
        )


def test_field_level_parity_detects_driver_mismatch(tmp_path):
    _, _, _, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)
    run, _ = service.run_from_file(context(), source, tmp_path / "Reports")

    run.records[0].driver = "Wrong Driver"
    parity = service._build_parity(run)

    assert {
        "contact_id": "C-1",
        "field_name": "driver",
        "expected_value": "Agent Behavior",
        "actual_value": "Wrong Driver",
    } in parity["mismatches"]


def test_field_level_parity_detects_classification_mismatch(tmp_path):
    _, _, _, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)
    run, _ = service.run_from_file(context(), source, tmp_path / "Reports")

    run.records[0].classification = "Promoter"
    parity = service._build_parity(run)

    assert {
        "contact_id": "C-1",
        "field_name": "classification",
        "expected_value": "Detractor",
        "actual_value": "Promoter",
    } in parity["mismatches"]


def test_field_level_parity_detects_sub_driver_mismatch(tmp_path):
    _, _, _, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)
    run, _ = service.run_from_file(context(), source, tmp_path / "Reports")

    run.records[0].sub_driver = "Wrong Sub Driver"
    parity = service._build_parity(run)

    assert {
        "contact_id": "C-1",
        "field_name": "sub_driver",
        "expected_value": "Empathy",
        "actual_value": "Wrong Sub Driver",
    } in parity["mismatches"]


def test_field_level_parity_detects_category_mismatch(tmp_path):
    _, _, _, service = create_service(tmp_path)
    source = write_csat_export(tmp_path)
    run, _ = service.run_from_file(context(), source, tmp_path / "Reports")

    run.records[0].csat_category = "Promoter"
    parity = service._build_parity(run)

    assert {
        "contact_id": "C-1",
        "field_name": "csat_category",
        "expected_value": "DSAT",
        "actual_value": "Promoter",
    } in parity["mismatches"]
