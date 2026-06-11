from app.domain.performance.value_objects._enum import GovernedEnum


class CoachingNoteVisibility(GovernedEnum):
    SHARED = "SHARED"
    MANAGER_ONLY = "MANAGER_ONLY"
    LEADERSHIP_ONLY = "LEADERSHIP_ONLY"
