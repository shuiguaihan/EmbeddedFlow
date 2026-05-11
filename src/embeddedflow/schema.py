from __future__ import annotations

from typing import Any


def validate_test_design_v1(data: dict[str, Any]) -> list[str]:
    """
    Validate a test_design_v1 document against the required structure.

    This is intentionally lightweight: it checks the contract shape needed by
    EmbeddedFlow without becoming a full schema engine.
    """
    errors: list[str] = []
    required = [
        "schema",
        "requirement",
        "stimulus",
        "observations",
        "pass_criteria",
        "automation_plan",
    ]
    for key in required:
        if key not in data:
            errors.append(f"missing required key: {key}")

    if data.get("schema") != "test_design_v1":
        errors.append("schema must be 'test_design_v1'")

    requirement = data.get("requirement")
    if not isinstance(requirement, str) or not requirement.strip():
        errors.append("requirement must be a non-empty string")

    stimulus = data.get("stimulus")
    if not isinstance(stimulus, dict):
        errors.append("stimulus must be a mapping")
    elif not isinstance(stimulus.get("type"), str) or not stimulus.get("type"):
        errors.append("stimulus must include non-empty type")

    _validate_list_of_typed_mappings(data.get("observations"), "observations", errors)
    _validate_list_of_typed_mappings(data.get("pass_criteria"), "pass_criteria", errors)

    automation_plan = data.get("automation_plan")
    if not isinstance(automation_plan, dict):
        errors.append("automation_plan must be a mapping")
    else:
        for key in ("automated", "manual"):
            value = automation_plan.get(key)
            if not isinstance(value, list):
                errors.append(f"automation_plan.{key} must be a list")

    return errors


def validate_schema(schema_name: str, data: dict[str, Any]) -> list[str]:
    if schema_name == "test_design_v1":
        return validate_test_design_v1(data)
    raise ValueError(f"unknown schema: {schema_name}")


def _validate_list_of_typed_mappings(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field} must be a non-empty list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{index}] must be a mapping")
            continue
        for key in ("id", "type"):
            if not isinstance(item.get(key), str) or not item.get(key):
                errors.append(f"{field}[{index}] must include non-empty {key}")
