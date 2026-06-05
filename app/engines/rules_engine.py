from app.core.metric import Metric
from app.core.rule import RuleResult
from app.core.framework import Framework


class RulesEngine:
    """
    Evaluates framework rules
    against metrics.
    """

    def evaluate_metric(
        self,
        framework: Framework,
        metric: Metric
    ) -> list[RuleResult]:

        results: list[RuleResult] = []

        rules = framework.get_rules_for_metric(
            metric.name
        )

        for rule in rules:

            result = rule.evaluate(
                metric.value
            )

            results.append(
                result
            )

        return results

    def evaluate_metrics(
        self,
        framework: Framework,
        metrics: list[Metric]
    ) -> list[RuleResult]:

        results: list[RuleResult] = []

        for metric in metrics:

            metric_results = self.evaluate_metric(
                framework,
                metric
            )

            results.extend(
                metric_results
            )

        return results
    