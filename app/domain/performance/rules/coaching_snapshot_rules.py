COACHING_SESSION_IMMUTABLE_FIELDS = {
    "tenant_id",
    "employee_id",
    "session_owner_id",
    "performance_opportunity_id",
    "evidence_pack_id",
    "evidence_version_snapshot",
    "evidence_artifact_ids_snapshot",
    "risk_result_id",
    "risk_score_snapshot",
    "risk_level_snapshot",
    "risk_classification_snapshot",
    "risk_definition_version",
    "risk_rule_version",
    "coaching_version",
    "lineage_id",
    "created_by",
    "created_at",
}


def reject_snapshot_mutation(existing, candidate) -> None:
    for field_name in COACHING_SESSION_IMMUTABLE_FIELDS:
        if getattr(existing, field_name) != getattr(candidate, field_name):
            raise PermissionError("Coaching session snapshots are immutable.")
