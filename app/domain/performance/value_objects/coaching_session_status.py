from app.domain.performance.value_objects._enum import GovernedEnum


class CoachingSessionStatus(GovernedEnum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
