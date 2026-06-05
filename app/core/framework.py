from dataclasses import dataclass, field
from typing import Any, cast

from app.core.rule import Rule


@dataclass
class Framework:
    """
    Generic operational framework.

    Examples:
    - CSAT
    - Performance Management
    - Agile Operations
    - Scrum
    - Scrumban
    - Lean
    """

    name: str
    version: str = "1.0"
    description: str = ""
    rules: list[Rule] = field(
        default_factory=lambda: cast(
            list[Rule],
            []
        )
    )
    metadata: dict[str, Any] = field(
        default_factory=lambda: cast(
            dict[str, Any],
            {}
        )
    )

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def get_rules_for_metric(self, metric_name: str) -> list[Rule]:
        normalized_metric = metric_name.strip().lower()

        return [
            rule
            for rule in self.rules
            if rule.metric_name.strip().lower() == normalized_metric
        ]

    def has_rules(self) -> bool:
        return len(self.rules) > 0

    def get_metadata(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        return self.metadata.get(
            key,
            default
        )