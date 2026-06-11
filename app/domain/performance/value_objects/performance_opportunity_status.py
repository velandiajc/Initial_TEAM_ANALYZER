from app.domain.performance.value_objects._enum import GovernedEnum


class PerformanceOpportunityStatus(GovernedEnum):
    IDENTIFIED = "IDENTIFIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
