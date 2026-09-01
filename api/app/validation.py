from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from jsonschema import Draft202012Validator


def validate_structured_data(schema: dict[str, Any], data: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        details = []
        for error in errors[:8]:
            path = ".".join(str(part) for part in error.absolute_path) or "structured_data"
            details.append(f"{path}: {error.message}")
        raise ValueError("; ".join(details))


def iter_unknown_fields(schema: dict[str, Any], data: Any, path: str = "") -> Iterator[str]:
    """Reject unknown object keys when the template describes object properties."""
    if not isinstance(data, dict) or not isinstance(schema, dict):
        return
    properties = schema.get("properties")
    additional = schema.get("additionalProperties", True)
    if isinstance(properties, dict) and additional is False:
        for key in data:
            if key not in properties:
                yield f"{path + '.' if path else ''}{key}"
    if isinstance(properties, dict):
        for key, child_schema in properties.items():
            if key in data:
                yield from iter_unknown_fields(
                    child_schema, data[key], f"{path + '.' if path else ''}{key}"
                )
    if schema.get("type") == "array" and isinstance(data, list):
        item_schema = schema.get("items", {})
        for index, item in enumerate(data):
            yield from iter_unknown_fields(item_schema, item, f"{path}[{index}]")


def validate_template_data(schema: dict[str, Any], data: dict[str, Any]) -> None:
    validate_structured_data(schema, data)
    unknown = list(iter_unknown_fields(schema, data))
    if unknown:
        raise ValueError(f"unknown structured field(s): {', '.join(unknown[:8])}")
