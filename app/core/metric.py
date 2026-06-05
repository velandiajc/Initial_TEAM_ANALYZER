from dataclasses import dataclass


@dataclass
class Metric:
    """
    Generic measurable metric.

    Examples:
    - CSAT
    - QA
    - Adherence
    - Attendance
    - Sales Conversion
    - AHT
    """

    name: str
    value: float

    target: float | None = None
    minimum: float | None = None
    maximum: float | None = None

    unit: str = "%"
    source: str = "unknown"

    def has_target(self) -> bool:
        return self.target is not None

    def is_above_target(self) -> bool:
        if self.target is None:
            return False

        return self.value >= self.target

    def is_below_minimum(self) -> bool:
        if self.minimum is None:
            return False

        return self.value < self.minimum

    def is_above_maximum(self) -> bool:
        if self.maximum is None:
            return False

        return self.value > self.maximum

    def variance_to_target(self) -> float:
        if self.target is None:
            return 0.0

        return self.value - self.target