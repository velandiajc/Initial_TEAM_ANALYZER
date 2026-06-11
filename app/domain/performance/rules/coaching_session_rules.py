from app.domain.performance.value_objects import CoachingSessionStatus


TRANSITIONS = {
    CoachingSessionStatus.DRAFT: {
        CoachingSessionStatus.OPEN,
        CoachingSessionStatus.CANCELLED,
    },
    CoachingSessionStatus.OPEN: {
        CoachingSessionStatus.IN_PROGRESS,
        CoachingSessionStatus.COMPLETED,
        CoachingSessionStatus.CANCELLED,
    },
    CoachingSessionStatus.IN_PROGRESS: {
        CoachingSessionStatus.COMPLETED,
        CoachingSessionStatus.CANCELLED,
    },
    CoachingSessionStatus.COMPLETED: set(),
    CoachingSessionStatus.CANCELLED: set(),
}


def validate_session_transition(current, target) -> None:
    current = CoachingSessionStatus.from_value(current)
    target = CoachingSessionStatus.from_value(target)
    if target not in TRANSITIONS[current]:
        raise ValueError(
            f"Invalid coaching session transition: "
            f"{current.value} -> {target.value}."
        )
