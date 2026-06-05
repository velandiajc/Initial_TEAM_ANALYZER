from dataclasses import dataclass


@dataclass
class AgentScorecard:
    agent_name: str
    agent_id: str
    email: str
    supervisor: str
    csat_mtd: str
    qa_mtd: str
    detractors: str
    open_dsat: str
    risk_level: str
    critical_flag: str
    main_dsat_driver: str
    qa_main_gap: str
    coaching_focus: str
    coaching_needed: str
    coaching_action: str
    coaching_topic: str
    coaching_reason: str
    schedule: str
    supervisor_recommendation: str


@dataclass
class AgentScorecardReport:
    workbook_path: str
    sheet_name: str
    scorecards: list[AgentScorecard]
    discovered_entities: list[str]
