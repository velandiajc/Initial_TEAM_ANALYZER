from app.domain.performance.value_objects._enum import GovernedEnum


class FollowUpStatus(GovernedEnum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
