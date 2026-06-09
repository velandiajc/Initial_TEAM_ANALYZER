from typing import Protocol

from app.models.risk import (
    RiskAssessmentRequest,
    RiskLevel,
    RiskRuleEvaluation,
    RiskRuleVersion,
)


class RiskRuleHandler(Protocol):
    def evaluate(
        self,
        request: RiskAssessmentRequest,
        rule_version: RiskRuleVersion
    ) -> RiskRuleEvaluation:
        ...


class RiskRuleHandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, RiskRuleHandler] = {}

    def register(
        self,
        key: str,
        handler: RiskRuleHandler
    ) -> None:
        normalized_key = self._normalize_key(key)

        if not normalized_key:
            raise ValueError("Risk rule handler key is required.")

        if normalized_key in self._handlers:
            raise ValueError(
                f"Risk rule handler already registered: {normalized_key}"
            )

        if not hasattr(handler, "evaluate"):
            raise TypeError("Risk rule handler must provide an evaluate method.")

        self._handlers[normalized_key] = handler

    def get_handler(self, key: str) -> RiskRuleHandler | None:
        normalized_key = self._normalize_key(key)

        if not normalized_key:
            raise ValueError("Risk rule handler key is required.")

        return self._handlers.get(normalized_key)

    def require_handler(self, key: str) -> RiskRuleHandler:
        handler = self.get_handler(key)

        if handler is None:
            raise KeyError(f"Unknown risk rule handler: {key}")

        return handler

    def _normalize_key(self, key: str) -> str:
        return str(key).strip().lower()


class ThresholdRiskRuleHandler:
    SUPPORTED_OPERATORS = {
        "lt",
        "lte",
        "gt",
        "gte",
        "eq",
        "neq",
        "between",
    }

    def evaluate(
        self,
        request: RiskAssessmentRequest,
        rule_version: RiskRuleVersion
    ) -> RiskRuleEvaluation:
        parameters = rule_version.parameters
        metric_name = _require_parameter(parameters, "metric_name")
        operator = _require_parameter(parameters, "operator").strip().lower()
        threshold = parameters.get("threshold")

        if operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(f"Unsupported threshold operator: {operator}")

        if metric_name not in request.metric_values:
            raise ValueError(f"Missing risk metric: {metric_name}")

        actual_value = float(request.metric_values[metric_name])
        triggered = self._compare(
            actual_value,
            operator,
            threshold
        )
        risk_level = RiskLevel.from_value(
            parameters.get("risk_level", RiskLevel.LOW.value)
        )
        default_level = RiskLevel.from_value(
            parameters.get("default_risk_level", RiskLevel.LOW.value)
        )
        reason = str(
            parameters.get("reason")
            or f"{metric_name} {operator} {threshold}"
        )

        return RiskRuleEvaluation(
            risk_level=risk_level if triggered else default_level,
            reason=reason if triggered else "No governed risk threshold matched.",
            triggered=triggered,
            evidence={
                "metric_name": metric_name,
                "operator": operator,
                "threshold": threshold,
                "actual_value": actual_value,
                "triggered": triggered,
            },
        )

    def _compare(
        self,
        actual_value: float,
        operator: str,
        threshold
    ) -> bool:
        if operator == "between":
            if not isinstance(threshold, list | tuple) or len(threshold) != 2:
                raise ValueError("Between operator requires two threshold values.")

            lower, upper = threshold
            return float(lower) <= actual_value <= float(upper)

        threshold_value = float(threshold)

        if operator == "lt":
            return actual_value < threshold_value

        if operator == "lte":
            return actual_value <= threshold_value

        if operator == "gt":
            return actual_value > threshold_value

        if operator == "gte":
            return actual_value >= threshold_value

        if operator == "eq":
            return actual_value == threshold_value

        if operator == "neq":
            return actual_value != threshold_value

        return False


def _require_parameter(parameters: dict, key: str) -> str:
    value = parameters.get(key)

    if not str(value).strip():
        raise ValueError(f"Risk rule parameter is required: {key}")

    return str(value)
