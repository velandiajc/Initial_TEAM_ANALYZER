from app.domain.performance.value_objects import CommitmentStatus


TRANSITIONS = {
    CommitmentStatus.OPEN: {
        CommitmentStatus.IN_PROGRESS,
        CommitmentStatus.COMPLETED,
        CommitmentStatus.MISSED,
        CommitmentStatus.CANCELLED,
    },
    CommitmentStatus.IN_PROGRESS: {
        CommitmentStatus.COMPLETED,
        CommitmentStatus.MISSED,
        CommitmentStatus.CANCELLED,
    },
    CommitmentStatus.COMPLETED: set(),
    CommitmentStatus.MISSED: set(),
    CommitmentStatus.CANCELLED: set(),
}


def validate_commitment_transition(current, target) -> None:
    current = CommitmentStatus.from_value(current)
    target = CommitmentStatus.from_value(target)
    if target not in TRANSITIONS[current]:
        raise ValueError(
            f"Invalid commitment transition: "
            f"{current.value} -> {target.value}."
        )
