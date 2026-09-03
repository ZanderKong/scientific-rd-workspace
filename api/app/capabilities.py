from __future__ import annotations

from typing import Any

from app.models import OBJECT_KINDS, RELATION_TYPES


def capabilities() -> dict[str, Any]:
    return {
        "api_contract_version": 1,
        "object_kinds": list(OBJECT_KINDS),
        "relation_types": list(RELATION_TYPES),
        "payload_kinds": ["scalar", "xy_series", "table", "file"],
        "features": {
            "sample_record": True,
            "experiment_membership": True,
            "experiment_comparison": True,
            "sample_execution": True,
            "change_sets": True,
            "idempotency": True,
            "optimistic_concurrency": True,
        },
        "write_policy": {"external_agent_default": "proposal", "unit_conversion": False},
    }
