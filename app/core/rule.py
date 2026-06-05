from dataclasses import dataclass, field
from typing import Any, Literal, cast


RuleOperator = Literal[
    "lt",
    "lte",
    "gt",
    "gte",
    "eq",
    "neq",
    "between"
]


@dataclass
class RuleResult:
    rule_name: str
    passed: bool
    severity: str
    message: str
    metadata: dict[str, Any] = field(
        default_factory=lambda: cast(
            dict[str, Any],
            {}
        )
    )


@dataclass
class Rule:
    """
    Generic configurable rule.

    Examples:
    - CSAT < 80 => Critical Risk
    - QA < 90 => Coaching Needed
    - Detractors >= 2 => Supervisor Review
    """

    name: str
    metric_name: str
    operator: RuleOperator
    threshold: float | tuple[float, float]
    severity: str = "moderate"
    message: str = ""

    def evaluate(self, value: float) -> RuleResult:
        passed = self._compare(value)

        return RuleResult(
            rule_name=self.name,
            passed=passed,
            severity=self.severity,
            message=self.message,
            metadata={
                "metric_name": self.metric_name,
                "operator": self.operator,
                "threshold": self.threshold,
                "actual_value": value
            }
        )
    def _compare(self, value: float) -> bool:

        if isinstance(self.threshold, tuple):

            if self.operator == "between":
                lower, upper = self.threshold
                return lower <= value <= upper

            return False

        threshold = float(self.threshold)

        if self.operator == "lt":
            return value < threshold

        if self.operator == "lte":
            return value <= threshold

        if self.operator == "gt":
            return value > threshold

        if self.operator == "gte":
            return value >= threshold

        if self.operator == "eq":
            return value == threshold

        if self.operator == "neq":
            return value != threshold

        return False

    def _get_range(self) -> tuple[float, float]:
        if not isinstance(self.threshold, tuple):
            raise ValueError(
                "Between operator requires threshold as tuple[float, float]"
            )

        lower, upper = self.threshold

        return float(lower), float(upper)