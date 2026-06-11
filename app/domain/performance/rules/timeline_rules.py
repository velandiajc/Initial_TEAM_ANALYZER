from app.domain.performance.rules.coaching_lineage_rules import (
    require_lineage_id,
    require_text,
)


def validate_timeline_reference(
    employee_id: str,
    source_entity_id: str,
    lineage_id: str,
) -> None:
    require_text(employee_id, "employee_id")
    require_text(source_entity_id, "source_entity_id")
    require_lineage_id(lineage_id)
