from app.domain.operational_impact.value_objects import (
    ImpactLevel,
    PriorityLevel,
)


def require_text(value, field_name):
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    return text


def require_items(value, field_name):
    if not value:
        raise ValueError(f"{field_name} is required.")
    return value


def validate_score(value, field_name):
    score = float(value)
    if not 0 <= score <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100.")
    return round(score, 4)


def classify_impact(score):
    score = validate_score(score, "impact_score")
    if score < 25:
        return ImpactLevel.LOW
    if score < 50:
        return ImpactLevel.MODERATE
    if score < 75:
        return ImpactLevel.HIGH
    return ImpactLevel.CRITICAL


def classify_priority(score):
    score = validate_score(score, "priority_score")
    if score < 25:
        return PriorityLevel.MONITOR
    if score < 50:
        return PriorityLevel.COACH
    if score < 75:
        return PriorityLevel.ESCALATE
    return PriorityLevel.IMMEDIATE_INTERVENTION


def normalize_factor_score(value, minimum, maximum, direction):
    value = float(value)
    minimum = float(minimum)
    maximum = float(maximum)
    if minimum >= maximum:
        raise ValueError("threshold_min must be less than threshold_max.")
    normalized = (value - minimum) / (maximum - minimum) * 100
    normalized = min(100.0, max(0.0, normalized))
    if direction.value == "LOWER_IS_WORSE":
        normalized = 100.0 - normalized
    return round(normalized, 4)


def is_material_change(
    previous_impact,
    current_impact,
    previous_priority,
    current_priority,
):
    impact_rank = {
        ImpactLevel.LOW: 0,
        ImpactLevel.MODERATE: 1,
        ImpactLevel.HIGH: 2,
        ImpactLevel.CRITICAL: 3,
    }
    priority_rank = {
        PriorityLevel.MONITOR: 0,
        PriorityLevel.COACH: 1,
        PriorityLevel.ESCALATE: 2,
        PriorityLevel.IMMEDIATE_INTERVENTION: 3,
    }
    impact_changed = (
        previous_impact != current_impact
        and max(
            impact_rank[previous_impact],
            impact_rank[current_impact],
        ) >= impact_rank[ImpactLevel.HIGH]
    )
    priority_changed = (
        previous_priority != current_priority
        and max(
            priority_rank[previous_priority],
            priority_rank[current_priority],
        ) >= priority_rank[PriorityLevel.ESCALATE]
    )
    return impact_changed or priority_changed
