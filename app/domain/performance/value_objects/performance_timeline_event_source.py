from app.domain.performance.value_objects._enum import GovernedEnum


class PerformanceTimelineEventSource(GovernedEnum):
    KPI = "KPI"
    RISK = "RISK"
    EVIDENCE = "EVIDENCE"
    COACHING = "COACHING"
    FOLLOWUP = "FOLLOWUP"
    COMMITMENT = "COMMITMENT"
    MANUAL = "MANUAL"
