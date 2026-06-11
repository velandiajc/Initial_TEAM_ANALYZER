from app.domain.performance.value_objects import PerformanceOpportunityStatus


TRANSITIONS = {
    PerformanceOpportunityStatus.IDENTIFIED: {
        PerformanceOpportunityStatus.UNDER_REVIEW,
        PerformanceOpportunityStatus.ACCEPTED,
        PerformanceOpportunityStatus.CANCELLED,
    },
    PerformanceOpportunityStatus.UNDER_REVIEW: {
        PerformanceOpportunityStatus.ACCEPTED,
        PerformanceOpportunityStatus.CANCELLED,
    },
    PerformanceOpportunityStatus.ACCEPTED: {
        PerformanceOpportunityStatus.CLOSED,
        PerformanceOpportunityStatus.CANCELLED,
    },
    PerformanceOpportunityStatus.CLOSED: set(),
    PerformanceOpportunityStatus.CANCELLED: set(),
}


def validate_opportunity_transition(current, target) -> None:
    current = PerformanceOpportunityStatus.from_value(current)
    target = PerformanceOpportunityStatus.from_value(target)
    if target not in TRANSITIONS[current]:
        raise ValueError(
            f"Invalid performance opportunity transition: "
            f"{current.value} -> {target.value}."
        )
