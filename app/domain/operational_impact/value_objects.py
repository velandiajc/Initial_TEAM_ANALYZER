from enum import Enum


class GovernedEnum(Enum):
    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        normalized = (
            str(value)
            .strip()
            .upper()
            .replace(" ", "_")
            .replace("-", "_")
        )
        for item in cls:
            if item.value == normalized or item.name == normalized:
                return item
        raise ValueError(f"Unsupported {cls.__name__}: {value}")


class ImpactGovernanceStatus(GovernedEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class ImpactDirection(GovernedEnum):
    HIGHER_IS_WORSE = "HIGHER_IS_WORSE"
    LOWER_IS_WORSE = "LOWER_IS_WORSE"


class ImpactLevel(GovernedEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PriorityLevel(GovernedEnum):
    MONITOR = "MONITOR"
    COACH = "COACH"
    ESCALATE = "ESCALATE"
    IMMEDIATE_INTERVENTION = "IMMEDIATE_INTERVENTION"


class OperationalImpactAuditEvent(GovernedEnum):
    OPERATIONAL_IMPACT_DEFINITION_CREATED = (
        "OPERATIONAL_IMPACT_DEFINITION_CREATED"
    )
    OPERATIONAL_IMPACT_DEFINITION_APPROVED = (
        "OPERATIONAL_IMPACT_DEFINITION_APPROVED"
    )
    OPERATIONAL_IMPACT_FACTOR_CREATED = "OPERATIONAL_IMPACT_FACTOR_CREATED"
    OPERATIONAL_IMPACT_FACTOR_APPROVED = "OPERATIONAL_IMPACT_FACTOR_APPROVED"
    OPERATIONAL_IMPACT_CALCULATED = "OPERATIONAL_IMPACT_CALCULATED"
    OPERATIONAL_IMPACT_VIEWED = "OPERATIONAL_IMPACT_VIEWED"
    OPERATIONAL_IMPACT_REJECTED = "OPERATIONAL_IMPACT_REJECTED"
    OPERATIONAL_IMPACT_CALCULATION_FAILED = (
        "OPERATIONAL_IMPACT_CALCULATION_FAILED"
    )
    OPERATIONAL_IMPACT_ACCESS_DENIED = "OPERATIONAL_IMPACT_ACCESS_DENIED"
    RISK_PRIORITY_CALCULATED = "RISK_PRIORITY_CALCULATED"
    RISK_PRIORITY_VIEWED = "RISK_PRIORITY_VIEWED"
    RISK_PRIORITY_REJECTED = "RISK_PRIORITY_REJECTED"
    RISK_PRIORITY_CALCULATION_FAILED = "RISK_PRIORITY_CALCULATION_FAILED"
    RISK_PRIORITY_ACCESS_DENIED = "RISK_PRIORITY_ACCESS_DENIED"
    OPERATIONAL_IMPACT_TIMELINE_EVENT_CREATED = (
        "OPERATIONAL_IMPACT_TIMELINE_EVENT_CREATED"
    )
