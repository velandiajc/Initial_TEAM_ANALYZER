from openpyxl import Workbook

from app.services.agent_scorecard_service import AgentScorecardService


def create_roaster_workbook(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roaster"
    sheet.append(["Roaster Performance Snapshot"])
    sheet.append([])
    sheet.append([])
    sheet.append(["Generated for Sprint 1 demo"])
    sheet.append(
        [
            "Name",
            "ID",
            "Email",
            "Supervisor",
            "CSAT MTD",
            "Detractors",
            "Open DSAT",
            "QA MTD",
            "Main DSAT Driver",
            "QA Main Gap",
            "Risk_Final",
            "Coaching Focus",
            "Coaching Needed",
            "Coaching Action (Auto)",
            "Coaching Topic (Auto)",
            "Coaching Reason (Auto)",
            "Critical Flag",
            "Schedule",
        ]
    )
    sheet.append(
        [
            "Daniela Talero",
            "A001",
            "daniela@example.com",
            "Supervisor One",
            92,
            0,
            0,
            96,
            "",
            "",
            "Low",
            "Maintain empathy",
            "No",
            "Monitor",
            "CX basics",
            "Strong current results",
            "No",
            "Morning",
        ]
    )
    sheet.append([None for _ in range(18)])
    sheet.append(
        [
            "Nicole Molina",
            "A002",
            "nicole@example.com",
            "Supervisor Two",
            71,
            3,
            2,
            82,
            "Resolution",
            "Documentation",
            "High",
            "Ownership",
            "Yes",
            "Review DSAT calls",
            "Resolution quality",
            "Open DSAT volume",
            "Yes",
            "Evening",
        ]
    )
    workbook.save(path)


def create_minimal_roaster_workbook(path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Roaster"
    sheet.append(["Name", "ID"])
    sheet.append(["Cristian Pinto", "A003"])
    workbook.save(path)


def test_builds_scorecards_from_roaster_with_detected_header(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_roaster_workbook(workbook_path)

    report = AgentScorecardService().build_report(workbook_path)

    assert report.sheet_name == "Roaster"
    assert len(report.scorecards) == 2
    assert report.scorecards[0].agent_name == "Daniela Talero"
    assert report.scorecards[0].csat_mtd == "92"
    assert report.scorecards[0].qa_mtd == "96"
    assert report.scorecards[1].agent_name == "Nicole Molina"
    assert report.scorecards[1].critical_flag == "Yes"


def test_skips_blank_rows(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_roaster_workbook(workbook_path)

    report = AgentScorecardService().build_report(workbook_path)

    assert [
        scorecard.agent_name
        for scorecard in report.scorecards
    ] == [
        "Daniela Talero",
        "Nicole Molina",
    ]


def test_handles_missing_columns_gracefully(tmp_path):
    workbook_path = tmp_path / "minimal.xlsx"
    create_minimal_roaster_workbook(workbook_path)

    report = AgentScorecardService().build_report(workbook_path)
    scorecard = report.scorecards[0]
    markdown = AgentScorecardService().render_markdown(report)

    assert scorecard.agent_name == "Cristian Pinto"
    assert scorecard.email == ""
    assert scorecard.csat_mtd == ""
    assert "| Email | Not available |" in markdown
    assert "| CSAT MTD | Not available |" in markdown


def test_generates_supervisor_recommendation_from_risk_signals(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_roaster_workbook(workbook_path)

    report = AgentScorecardService().build_report(workbook_path)
    high_risk_scorecard = report.scorecards[1]

    assert "immediate supervisor follow-up" in (
        high_risk_scorecard.supervisor_recommendation
    )


def test_render_markdown_keeps_scorecards_readable(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    create_roaster_workbook(workbook_path)

    report = AgentScorecardService().build_report(workbook_path)
    markdown = AgentScorecardService().render_markdown(report)

    assert "# Agent Scorecards" in markdown
    assert "## Daniela Talero" in markdown
    assert "| Field | Value |" in markdown
    assert "| Supervisor recommendation |" in markdown


def test_write_report_creates_markdown_file(tmp_path):
    workbook_path = tmp_path / "team.xlsx"
    output_path = tmp_path / "Reports" / "Sprint_1_Demos" / "agent_scorecards.md"
    create_roaster_workbook(workbook_path)

    report = AgentScorecardService().write_report(
        workbook_path,
        output_path
    )

    markdown = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert len(report.scorecards) == 2
    assert "Daniela Talero" in markdown
    assert "Nicole Molina" in markdown
