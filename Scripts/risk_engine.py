import pandas as pd
from pathlib import Path

from app.services.pci_redaction_service import PCIRedactionService

FILE = Path("Data/Raw/Team JV - MAY.xlsx")
REPORTS = Path("Reports")
REPORTS.mkdir(exist_ok=True)


def load_table(sheet_name):
    raw = pd.read_excel(FILE, sheet_name=sheet_name, header=None)
    header_row = raw[raw.eq("Name").any(axis=1)].index[0]
    raw.columns = raw.iloc[header_row]
    df = raw.iloc[header_row + 1:].reset_index(drop=True)
    return df[df["Name"].notna()]


def load_roaster():
    df = load_table("Roaster")

    numeric_cols = [
        "CSAT MTD",
        "QA MTD",
        "Controllable DSAT",
        "Detractors",
        "Open DSAT",
        "Coaching Open",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_csat():
    df = pd.read_excel(FILE, sheet_name="MTD CSAT (raw data)")

    summary = df.groupby("Agent Clean").agg(
        Survey_Count=("OSAT", "count"),
        Avg_OSAT=("OSAT", "mean"),
        Detractor_Count=("Is_Detractor", lambda x: (x == "Y").sum()),
        Top_Customer_Reason=(
            "CSAT Category (Auto)",
            lambda x: x.mode().iloc[0] if not x.mode().empty else None,
        ),
    ).reset_index()

    return summary.rename(columns={"Agent Clean": "Name"})


def load_dsat():
    df = pd.read_excel(FILE, sheet_name="DSAT_Dashboard_Old")

    summary = df.groupby("Agent").agg(
        DSAT_Reviewed=("Status", lambda x: (x == "Reviewed").sum()),
        DSAT_Open=("Status", lambda x: (x == "New").sum()),
        Main_DSAT_Driver=(
            "Driver_Final",
            lambda x: x.dropna().mode().iloc[0] if not x.dropna().mode().empty else None,
        ),
        Main_DSAT_Severity=(
            "Severity",
            lambda x: x.dropna().mode().iloc[0] if not x.dropna().mode().empty else None,
        ),
    ).reset_index()

    return summary.rename(columns={"Agent": "Name"})


def load_coaching():
    df = pd.read_excel(FILE, sheet_name="Coaching follow-ups")

    summary = df.groupby("Agent").agg(
        Total_Coachings=("Status", "count"),
        Open_Coachings=("Status", lambda x: (x == "Open").sum()),
        Closed_Coachings=("Status", lambda x: (x == "Closed").sum()),
        Last_Coaching_Date=("Date", "max"),
        Last_Coaching_Topic=(
            "Topic",
            lambda x: x.dropna().iloc[-1] if not x.dropna().empty else None,
        ),
    ).reset_index()

    return summary.rename(columns={"Agent": "Name"})


def calculate_risk(row):
    if row["Status"] != "Active":
        return "Inactive"

    if (
        row["CSAT MTD"] < 80
        or row["QA MTD"] < 0.80
        or row["Controllable DSAT"] >= 4
    ):
        return "High"

    if (
        row["CSAT MTD"] < 90
        or row["QA MTD"] < 0.90
        or row["Controllable DSAT"] >= 2
    ):
        return "Moderate"

    return "Low"


def calculate_focus(row):
    if row["Risk_Calculated"] == "Inactive":
        return "None"

    qa = row["QA MTD"]
    csat = row["CSAT MTD"]
    dsat = row["Controllable DSAT"]

    if qa < 0.80 and (csat < 90 or dsat >= 1):
        return "Both"

    if qa < 0.80:
        return "QA"

    if csat < 90 or dsat >= 1:
        return "CSAT"

    if qa < 0.90:
        return "QA"

    return "None"


def calculate_needed(row):
    if row["Risk_Calculated"] == "Inactive":
        return "No"

    if row["Risk_Calculated"] == "High":
        return "Yes"

    if (
        row["CSAT MTD"] < 90
        or row["QA MTD"] < 0.90
        or row["Controllable DSAT"] >= 1
    ):
        return "Yes"

    return "No"


def calculate_action(row):
    if row["Risk_Calculated"] == "Inactive":
        return "No action"

    if row["Risk_Calculated"] == "High":
        return "Full coaching: QA + CSAT"

    if row["Risk_Calculated"] == "Moderate":
        if row["Coaching Open"] > 0:
            return "Quick follow-up"
        return "Review QA + coach specific gap"

    if row["Risk_Calculated"] == "Low":
        return "Maintain performance / flexible monitor"

    return "Review"


def calculate_reason(row):
    if row["Risk_Calculated"] == "Inactive":
        return "Inactive"

    qa = row["QA MTD"]
    csat = row["CSAT MTD"]
    dsat = row["Controllable DSAT"]
    gap = row.get("QA Main Gap", None)
    driver = row.get("Main_DSAT_Driver", None)

    reasons = []

    if csat < 90:
        reasons.append("CSAT below target")

    if qa < 0.90:
        reasons.append(f"QA gap: {gap}" if pd.notna(gap) else "QA below target")

    if dsat >= 1:
        reasons.append(f"DSAT driver: {driver}" if pd.notna(driver) else "Controllable DSAT")

    if not reasons:
        return "Stable performance"

    return " + ".join(reasons)


def calculate_critical_flag(row):
    if row["Status"] != "Active":
        return "No"

    if row["Risk_Calculated"] == "High":
        return "Critical"

    if (
        row["Risk_Calculated"] == "Moderate"
        and row["CSAT MTD"] < 85
        and row["Controllable DSAT"] >= 2
    ):
        return "Critical"

    return "No"


def create_leadership_summary(df):
    total_agents = len(df)
    active_agents = len(df[df["Status"] == "Active"])

    high_risk = df[df["Risk_Calculated"] == "High"]
    moderate_risk = df[df["Risk_Calculated"] == "Moderate"]
    low_risk = df[df["Risk_Calculated"] == "Low"]
    critical_agents = df[df["Critical_Flag_Calculated"] == "Critical"]

    avg_csat = df["CSAT MTD"].mean()
    avg_qa = df["QA MTD"].mean()

    top_dsat_drivers = (
        df["Main_DSAT_Driver"]
        .dropna()
        .value_counts()
        .head(5)
    )

    qa_gaps = (
        df["QA Main Gap"]
        .dropna()
        .value_counts()
        .head(5)
    )

    lines = []

    lines.append("TEAM JV - LEADERSHIP SUMMARY")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"Total Agents: {total_agents}")
    lines.append(f"Active Agents: {active_agents}")
    lines.append(f"Average CSAT: {avg_csat:.2f}")
    lines.append(f"Average QA: {avg_qa:.2%}")
    lines.append("")
    lines.append("RISK DISTRIBUTION")
    lines.append("-" * 50)
    lines.append(f"High Risk: {len(high_risk)}")
    lines.append(f"Moderate Risk: {len(moderate_risk)}")
    lines.append(f"Low Risk: {len(low_risk)}")
    lines.append(f"Critical Coaching Needed: {len(critical_agents)}")
    lines.append("")

    lines.append("HIGH RISK AGENTS")
    lines.append("-" * 50)

    if high_risk.empty:
        lines.append("No high-risk agents identified.")
    else:
        for _, row in high_risk.iterrows():
            lines.append(
                f"- {row['Name']} | CSAT: {row['CSAT MTD']:.2f} | "
                f"QA: {row['QA MTD']:.2%} | "
                f"Controllable DSAT: {row['Controllable DSAT']} | "
                f"Focus: {row['Coaching_Focus_Calculated']} | "
                f"Action: {row['Coaching_Action_Calculated']} | "
                f"Reason: {row['Coaching_Reason_Calculated']}"
            )

    lines.append("")
    lines.append("CRITICAL COACHING PRIORITIES")
    lines.append("-" * 50)

    if critical_agents.empty:
        lines.append("No critical coaching priorities identified.")
    else:
        for _, row in critical_agents.iterrows():
            lines.append(
                f"- {row['Name']} | Focus: {row['Coaching_Focus_Calculated']} | "
                f"Action: {row['Coaching_Action_Calculated']} | "
                f"Reason: {row['Coaching_Reason_Calculated']}"
            )

    lines.append("")
    lines.append("TOP DSAT DRIVERS")
    lines.append("-" * 50)

    if top_dsat_drivers.empty:
        lines.append("No DSAT drivers available.")
    else:
        for driver, count in top_dsat_drivers.items():
            lines.append(f"- {driver}: {count}")

    lines.append("")
    lines.append("TOP QA GAPS")
    lines.append("-" * 50)

    if qa_gaps.empty:
        lines.append("No QA gaps available.")
    else:
        for gap, count in qa_gaps.items():
            lines.append(f"- {gap}: {count}")

    lines.append("")
    lines.append("RECOMMENDED ACTIONS")
    lines.append("-" * 50)
    lines.append("1. Prioritize all High Risk agents for full coaching within the next 48 hours.")
    lines.append("2. For Critical agents, combine QA behavior review with CSAT/DSAT customer perception.")
    lines.append("3. Use QA Main Gap to define the behavior to monitor in the next QA review.")
    lines.append("4. Use Main DSAT Driver to define the customer experience coaching angle.")
    lines.append("5. Keep Moderate Risk agents under weekly follow-up until CSAT and QA stabilize.")

    summary = PCIRedactionService().redact("\n".join(lines))

    with open(REPORTS / "leadership_summary.txt", "w", encoding="utf-8") as file:
        file.write(summary)

def export_json(final):
    json_df = final.copy()

    json_df["QA MTD"] = json_df["QA MTD"].apply(
        lambda x: round(x * 100, 2) if pd.notna(x) else None
    )

    json_df["CSAT MTD"] = json_df["CSAT MTD"].apply(
        lambda x: round(x, 2) if pd.notna(x) else None
    )

    records = PCIRedactionService().redact_structure(
        json_df.to_dict(orient="records")
    )

    with open(REPORTS / "team_data.json", "w", encoding="utf-8") as file:
        import json
        json.dump(records, file, indent=4, ensure_ascii=False)
def main():

    roaster = load_roaster()
    csat = load_csat()
    dsat = load_dsat()
    coaching = load_coaching()

    df = roaster.merge(csat, on="Name", how="left")
    df = df.merge(dsat, on="Name", how="left")
    df = df.merge(coaching, on="Name", how="left")

    df["Risk_Calculated"] = df.apply(calculate_risk, axis=1)
    df["Coaching_Focus_Calculated"] = df.apply(calculate_focus, axis=1)
    df["Coaching_Needed_Calculated"] = df.apply(calculate_needed, axis=1)
    df["Coaching_Action_Calculated"] = df.apply(calculate_action, axis=1)
    df["Coaching_Reason_Calculated"] = df.apply(calculate_reason, axis=1)
    df["Critical_Flag_Calculated"] = df.apply(calculate_critical_flag, axis=1)

    final = df[
        [
            "Name",
            "Status",
            "CSAT MTD",
            "Survey_Count",
            "Avg_OSAT",
            "Detractors",
            "Detractor_Count",
            "Open DSAT",
            "Controllable DSAT",
            "QA MTD",
            "QA Main Gap",
            "Main_DSAT_Driver",
            "Main_DSAT_Severity",
            "Risk_Calculated",
            "Coaching_Focus_Calculated",
            "Coaching_Needed_Calculated",
            "Coaching_Action_Calculated",
            "Coaching_Reason_Calculated",
            "Critical_Flag_Calculated",
        ]
    ]

    pci_service = PCIRedactionService()
    safe_final = final.map(
        lambda value: (
            pci_service.redact(value)
            if isinstance(value, str)
            else value
        )
    )
    safe_final.to_csv(
        REPORTS / "combined_team_analysis.csv",
        index=False,
    )

    create_leadership_summary(safe_final)

    export_json(safe_final)

    print("Reports created:")
    print("Reports/combined_team_analysis.csv")
    print("Reports/leadership_summary.txt")
    print("Reports/team_data.json")
    
if __name__ == "__main__":
    main()
