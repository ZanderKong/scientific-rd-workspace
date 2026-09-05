from __future__ import annotations

from typing import Any

from app.models import OBJECT_KINDS, RELATION_TYPES


def capabilities() -> dict[str, Any]:
    return {
        "api_contract_version": "0.3",
        "object_kinds": list(OBJECT_KINDS),
        "relation_types": list(RELATION_TYPES),
        "representation_kinds": ["raw_file", "table", "image", "description", "structured"],
        "features": {
            "sample_record": True,
            "experiment_references": True,
            "process_definition_versions": True,
            "process_execution_bindings": True,
            "data_representations": True,
            "views": True,
            "claims": True,
            "assets": True,
            "change_sets": True,
            "idempotency": True,
            "optimistic_concurrency": True,
        },
        "write_policy": {"external_agent_default": "proposal", "unit_conversion": False},
    }
