import pandas as pd
import pytest

from app.services.workbook_inventory_service import WorkbookInventoryService


def create_workbook(path):
    long_value = "x" * 150

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Agent Name": [
                    "Agent One",
                    "Agent Two",
                    "Agent Three",
                    "Agent Four",
                    "Agent Five",
                    "Agent Six",
                ],
                "CSAT": [
                    95,
                    None,
                    82,
                    76,
                    91,
                    88,
                ],
                "Long Comment": [
                    long_value,
                    "Short",
                    "Another",
                    "More",
                    "Fifth",
                    "Sixth",
                ],
            }
        ).to_excel(
            writer,
            sheet_name="Survey Data",
            index=False
        )

        pd.DataFrame(
            {
                "Metric": [
                    "QA",
                    "AHT",
                ],
                "Value": [
                    0.92,
                    310,
                ],
            }
        ).to_excel(
            writer,
            sheet_name="Performance",
            index=False
        )

        pd.DataFrame(
            columns=[
                "Empty A",
                "Empty B",
            ]
        ).to_excel(
            writer,
            sheet_name="Empty Sheet",
            index=False
        )


def test_reads_workbook_with_multiple_sheets(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)

    inventory = WorkbookInventoryService().build_inventory(
        workbook_path
    )

    assert inventory.workbook_path == str(workbook_path)
    assert inventory.sheet_count == 3
    assert [
        sheet.sheet_name
        for sheet in inventory.sheets
    ] == [
        "Survey Data",
        "Performance",
        "Empty Sheet",
    ]


def test_reports_row_counts_column_counts_and_column_names(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)

    inventory = WorkbookInventoryService().build_inventory(
        workbook_path
    )

    survey_sheet = inventory.sheets[0]
    performance_sheet = inventory.sheets[1]
    empty_sheet = inventory.sheets[2]

    assert survey_sheet.row_count == 6
    assert survey_sheet.column_count == 3
    assert survey_sheet.column_names == [
        "Agent Name",
        "CSAT",
        "Long Comment",
    ]

    assert performance_sheet.row_count == 2
    assert performance_sheet.column_count == 2
    assert performance_sheet.column_names == [
        "Metric",
        "Value",
    ]

    assert empty_sheet.row_count == 0
    assert empty_sheet.column_count == 2
    assert empty_sheet.column_names == [
        "Empty A",
        "Empty B",
    ]


def test_includes_up_to_five_sample_rows(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)

    inventory = WorkbookInventoryService().build_inventory(
        workbook_path
    )

    assert len(inventory.sheets[0].sample_rows) == 5
    assert inventory.sheets[0].sample_rows[0]["Agent Name"] == "Agent One"
    assert inventory.sheets[0].sample_rows[-1]["Agent Name"] == "Agent Five"


def test_converts_nan_values_to_empty_strings(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)

    inventory = WorkbookInventoryService().build_inventory(
        workbook_path
    )

    assert inventory.sheets[0].sample_rows[1]["CSAT"] == ""


def test_truncates_long_cell_values_to_120_characters(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)

    inventory = WorkbookInventoryService().build_inventory(
        workbook_path
    )

    value = inventory.sheets[0].sample_rows[0]["Long Comment"]

    assert len(value) == 120
    assert value == "x" * 120


def test_handles_empty_sheets(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)

    inventory = WorkbookInventoryService().build_inventory(
        workbook_path
    )

    empty_sheet = inventory.sheets[2]

    assert empty_sheet.sheet_name == "Empty Sheet"
    assert empty_sheet.row_count == 0
    assert empty_sheet.sample_rows == []


def test_raises_file_not_found_for_missing_workbook(tmp_path):
    workbook_path = tmp_path / "missing.xlsx"

    with pytest.raises(
        FileNotFoundError,
        match="Workbook file not found"
    ):
        WorkbookInventoryService().build_inventory(
            workbook_path
        )


def test_raises_value_error_for_non_xlsx_input(tmp_path):
    workbook_path = tmp_path / "team.xls"
    workbook_path.write_text(
        "not an xlsx file",
        encoding="utf-8"
    )

    with pytest.raises(
        ValueError,
        match="only supports .xlsx files"
    ):
        WorkbookInventoryService().build_inventory(
            workbook_path
        )


def test_render_markdown_includes_sheet_inventory(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_workbook(workbook_path)
    service = WorkbookInventoryService()
    inventory = service.build_inventory(workbook_path)

    markdown = service.render_markdown(inventory)

    assert "# Workbook Inventory" in markdown
    assert f"**Workbook:** {workbook_path}" in markdown
    assert "**Sheet Count:** 3" in markdown
    assert "## Sheet: Survey Data" in markdown
    assert "- Row count: 6" in markdown
    assert "- Column count: 3" in markdown
    assert "- Agent Name" in markdown
    assert "| Agent Name | CSAT | Long Comment |" in markdown
    assert "## Sheet: Empty Sheet" in markdown
    assert "No sample rows." in markdown
