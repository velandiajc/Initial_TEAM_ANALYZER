from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.domain.operational_impact import (
    ImpactGovernanceStatus,
    OperationalImpactDefinition,
    OperationalImpactFactor,
)
from app.domain.operational_impact.rules import (
    classify_impact,
    classify_priority,
    is_material_change,
    normalize_factor_score,
)
from app.domain.operational_impact.value_objects import (
    ImpactLevel,
    PriorityLevel,
)


def definition(created_by="owner-1"):
    return OperationalImpactDefinition(
        impact_definition_id="impact",
        tenant_id="tenant-1",
        name="Operational Impact",
        description="Governed impact.",
        impact_category="performance",
        owner="owner-1",
        steward="steward-1",
        status=ImpactGovernanceStatus.DRAFT,
        impact_definition_version="1.0",
        effective_date=date(2026, 6, 1),
        created_by=created_by,
        updated_by=created_by,
    )


def factor(**overrides):
    values = {
        "impact_factor_id": "factor-1",
        "tenant_id": "tenant-1",
        "impact_definition_id": "impact",
        "impact_definition_version": "1.0",
        "name": "Survey Volume",
        "description": "Governed factor.",
        "source_reference": "kpi:survey-volume",
        "weight": 0.2,
        "direction": "HIGHER_IS_WORSE",
        "threshold_version": "1.0",
        "threshold_min": 0,
        "threshold_max": 100,
        "impact_factor_version": "1.0",
        "owner": "owner-1",
        "steward": "steward-1",
        "status": ImpactGovernanceStatus.DRAFT,
        "effective_date": date(2026, 6, 1),
        "created_by": "owner-1",
        "updated_by": "owner-1",
    }
    values.update(overrides)
    return OperationalImpactFactor(**values)


@pytest.mark.parametrize(
    "field_name",
    ["impact_definition_version", "owner", "steward"],
)
def test_definition_requires_version_owner_and_steward(field_name):
    values = {**definition().__dict__, field_name: ""}
    with pytest.raises(ValueError, match=field_name):
        definition().__class__(**values)


def test_creator_cannot_approve_own_definition_or_factor():
    with pytest.raises(PermissionError, match="Creator"):
        definition().approve("owner-1")
    with pytest.raises(PermissionError, match="Creator"):
        factor().approve("owner-1")


def test_approved_definition_and_factor_activate_with_versions_preserved():
    approved_definition = definition().approve("approver-1")
    active_definition = approved_definition.activate("approver-1")
    approved_factor = factor().approve("approver-1")
    active_factor = approved_factor.activate("approver-1")

    assert active_definition.status == ImpactGovernanceStatus.ACTIVE
    assert active_definition.impact_definition_version == "1.0"
    assert active_factor.status == ImpactGovernanceStatus.ACTIVE
    assert active_factor.threshold_version == "1.0"
    assert active_factor.weight == 0.2


def test_factor_rejects_raw_or_unversioned_sources():
    with pytest.raises(ValueError, match="governed"):
        factor(source_reference="transcript:raw")
    with pytest.raises(ValueError, match="threshold_version"):
        factor(threshold_version="")


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("impact_factor_version", "", "impact_factor_version"),
        ("weight", 0, "weight"),
        ("weight", 1.1, "weight"),
        ("threshold_min", 100, "threshold_min"),
    ],
)
def test_factor_requires_governed_weight_threshold_and_version(
    field_name,
    value,
    message,
):
    changes = {field_name: value}
    if field_name == "threshold_min":
        changes["threshold_max"] = 100
    with pytest.raises(ValueError, match=message):
        factor(**changes)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, ImpactLevel.LOW),
        (25, ImpactLevel.MODERATE),
        (50, ImpactLevel.HIGH),
        (75, ImpactLevel.CRITICAL),
    ],
)
def test_impact_level_thresholds(score, expected):
    assert classify_impact(score) == expected


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, PriorityLevel.MONITOR),
        (25, PriorityLevel.COACH),
        (50, PriorityLevel.ESCALATE),
        (75, PriorityLevel.IMMEDIATE_INTERVENTION),
    ],
)
def test_priority_level_thresholds(score, expected):
    assert classify_priority(score) == expected


def test_factor_normalization_honors_direction():
    assert normalize_factor_score(20, 0, 100, factor().direction) == 20
    lower_is_worse = factor(direction="LOWER_IS_WORSE")
    assert normalize_factor_score(20, 0, 100, lower_is_worse.direction) == 80


def test_material_change_suppresses_noise_and_records_high_consequence():
    assert not is_material_change(
        ImpactLevel.LOW,
        ImpactLevel.MODERATE,
        PriorityLevel.MONITOR,
        PriorityLevel.COACH,
    )
    assert is_material_change(
        ImpactLevel.MODERATE,
        ImpactLevel.HIGH,
        PriorityLevel.COACH,
        PriorityLevel.ESCALATE,
    )


def test_governed_definition_is_frozen():
    item = definition()
    with pytest.raises(FrozenInstanceError):
        item.name = "Rewritten"
