class WorkspaceLineageRules:
    def require(self, references):
        values = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in references
                if str(value).strip()
            )
        )
        if not values:
            raise ValueError("Workspace lineage references are required.")
        return values

    def priority_references(self, priority, impact):
        if priority.tenant_id != impact.tenant_id:
            raise PermissionError("Priority and impact tenant mismatch.")
        if priority.impact_assessment_id != impact.impact_assessment_id:
            raise ValueError("Priority does not reference impact assessment.")
        references = [
            f"priority_assessment:{priority.priority_assessment_id}",
            f"priority_lineage:{priority.lineage_id}",
            f"risk_result:{priority.risk_result_id}",
            f"risk_definition_version:{priority.risk_definition_version}",
            f"risk_rule_version:{priority.risk_rule_version}",
            f"impact_assessment:{impact.impact_assessment_id}",
            f"impact_lineage:{impact.lineage_id}",
            f"impact_definition_version:{impact.impact_definition_version}",
        ]
        references.extend(
            f"impact_factor_version:{factor_id}:{version}"
            for factor_id, version in sorted(
                impact.impact_factor_versions.items()
            )
        )
        references.extend(
            f"impact_threshold_version:{factor_id}:{version}"
            for factor_id, version in sorted(
                impact.threshold_versions.items()
            )
        )
        references.extend(
            f"kpi_result:{result_id}"
            for result_id in impact.source_kpi_result_ids
        )
        references.extend(
            f"risk_result:{result_id}"
            for result_id in impact.source_risk_result_ids
        )
        return self.require(references)

    def collect(self, *groups):
        references = []
        for group in groups:
            if group is None:
                continue
            if isinstance(group, str):
                references.append(group)
                continue
            references.extend(group)
        return self.require(references)
