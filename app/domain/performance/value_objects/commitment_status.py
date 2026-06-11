from app.domain.performance.value_objects._enum import GovernedEnum


class CommitmentStatus(GovernedEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
