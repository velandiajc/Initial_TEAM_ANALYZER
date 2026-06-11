from app.domain.performance.value_objects import FollowUpStatus


TRANSITIONS = {
    FollowUpStatus.SCHEDULED: {
        FollowUpStatus.COMPLETED,
        FollowUpStatus.MISSED,
        FollowUpStatus.CANCELLED,
    },
    FollowUpStatus.COMPLETED: set(),
    FollowUpStatus.MISSED: set(),
    FollowUpStatus.CANCELLED: set(),
}


def validate_followup_transition(current, target) -> None:
    current = FollowUpStatus.from_value(current)
    target = FollowUpStatus.from_value(target)
    if target not in TRANSITIONS[current]:
        raise ValueError(
            f"Invalid follow-up transition: "
            f"{current.value} -> {target.value}."
        )
