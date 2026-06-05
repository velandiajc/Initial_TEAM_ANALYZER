from app.services.workbook_entity_discovery_service import (
    WorkbookEntityDiscoveryService,
)
from app.services.workbook_ingestion_service import (
    WorkbookInventory,
    WorksheetInventory,
)


def create_inventory():
    return WorkbookInventory(
        workbook_path="operations.xlsx",
        sheet_count=3,
        sheets=[
            WorksheetInventory(
                sheet_name="Roaster",
                row_count=2,
                column_count=6,
                header_row_number=5,
                column_names=[
                    "Agent Name",
                    "ID",
                    "Email",
                    "Supervisor",
                    "Attendance",
                    "Schedule",
                ],
                sample_rows=[],
            ),
            WorksheetInventory(
                sheet_name="QA_WORK",
                row_count=2,
                column_count=8,
                header_row_number=5,
                column_names=[
                    "Agent Name",
                    "QA MTD",
                    "QA Coverage Status",
                    "CSAT MTD",
                    "Detractors",
                    "Open DSAT",
                    "Coaching Focus",
                    "Coaching Needed",
                ],
                sample_rows=[],
            ),
            WorksheetInventory(
                sheet_name="Control Panel",
                row_count=2,
                column_count=6,
                header_row_number=4,
                column_names=[
                    "Risk_Final",
                    "Critical Flag",
                    "Priority Score",
                    "Adherence",
                    "Workforce Group",
                    "Supervisor Schedule",
                ],
                sample_rows=[],
            ),
        ],
    )


def discoveries_by_entity(discoveries):
    return {
        discovery.entity: discovery
        for discovery in discoveries
    }


def test_discovers_agent_columns():
    report = WorkbookEntityDiscoveryService().discover(create_inventory())
    roaster_discoveries = [
        discovery
        for discovery in report.discoveries
        if discovery.sheet_name == "Roaster"
    ]

    agent = discoveries_by_entity(roaster_discoveries)["Agent"]

    assert agent.columns == [
        "Agent Name",
        "ID",
        "Email",
        "Supervisor",
    ]
    assert agent.confidence >= 0.9


def test_discovers_qa_csat_and_coaching_columns():
    report = WorkbookEntityDiscoveryService().discover(create_inventory())
    qa_work_discoveries = [
        discovery
        for discovery in report.discoveries
        if discovery.sheet_name == "QA_WORK"
    ]
    by_entity = discoveries_by_entity(qa_work_discoveries)

    assert by_entity["QA"].columns == [
        "QA MTD",
        "QA Coverage Status",
    ]
    assert by_entity["CSAT"].columns == [
        "CSAT MTD",
        "Detractors",
        "Open DSAT",
    ]
    assert by_entity["Coaching"].columns == [
        "Coaching Focus",
        "Coaching Needed",
    ]


def test_discovers_risk_workforce_adherence_and_schedule_columns():
    report = WorkbookEntityDiscoveryService().discover(create_inventory())
    control_panel_discoveries = [
        discovery
        for discovery in report.discoveries
        if discovery.sheet_name == "Control Panel"
    ]
    by_entity = discoveries_by_entity(control_panel_discoveries)

    assert by_entity["Risk"].columns == [
        "Risk_Final",
        "Critical Flag",
        "Priority Score",
    ]
    assert by_entity["Adherence"].columns == ["Adherence"]
    assert by_entity["Workforce"].columns == ["Workforce Group"]
    assert by_entity["Schedule"].columns == ["Supervisor Schedule"]


def test_parses_inventory_markdown_and_discovers_entities(tmp_path):
    inventory_path = tmp_path / "workbook_inventory.md"
    inventory_path.write_text(
        "\n".join(
            [
                "# Workbook Inventory",
                "",
                "**Workbook:** operations.xlsx",
                "**Sheet Count:** 1",
                "",
                "## Sheet: QA_WORK",
                "",
                "- Row count: 2",
                "- Column count: 4",
                "- Detected header row: 5",
                "",
                "### Columns",
                "",
                "- Agent Name",
                "- QA MTD",
                "- CSAT MTD",
                "- Risk_Final",
                "",
                "### Sample Rows",
                "",
                "| Agent Name | QA MTD | CSAT MTD | Risk_Final |",
                "|---|---|---|---|",
            ]
        ),
        encoding="utf-8",
    )

    report = WorkbookEntityDiscoveryService().discover_from_inventory_markdown(
        inventory_path
    )
    entities = {
        discovery.entity
        for discovery in report.discoveries
    }

    assert report.sheet_count == 1
    assert entities == {"Agent", "QA", "CSAT", "Risk"}


def test_render_markdown_contains_required_columns():
    service = WorkbookEntityDiscoveryService()
    report = service.discover(create_inventory())

    markdown = service.render_markdown(report)

    assert "# Workbook Entity Discovery" in markdown
    assert "| Sheet | Entity | Columns | Confidence |" in markdown
    assert "| QA_WORK | QA | QA MTD, QA Coverage Status |" in markdown


def test_write_report_creates_workbook_entities_markdown(tmp_path):
    inventory_path = tmp_path / "workbook_inventory.md"
    output_path = tmp_path / "workbook_entities.md"
    inventory_path.write_text(
        "\n".join(
            [
                "# Workbook Inventory",
                "",
                "**Workbook:** operations.xlsx",
                "**Sheet Count:** 1",
                "",
                "## Sheet: Control Panel",
                "",
                "- Row count: 1",
                "- Column count: 3",
                "- Detected header row: 1",
                "",
                "### Columns",
                "",
                "- Risk_Final",
                "- Critical Flag",
                "- Priority Score",
            ]
        ),
        encoding="utf-8",
    )

    WorkbookEntityDiscoveryService().write_report(
        inventory_path,
        output_path
    )

    markdown = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert "| Control Panel | Risk | Risk_Final, Critical Flag, Priority Score |" in markdown
