from __future__ import annotations

from typing import Any

from app.models import OBJECT_KINDS, RELATION_TYPES


def capabilities() -> dict[str, Any]:
    return {
        "api_contract_version": "1.5",
        "object_kinds": list(OBJECT_KINDS),
        "relation_types": list(RELATION_TYPES),
        "representation_kinds": ["raw_file", "table", "image", "description", "structured"],
        "features": {
            "sample_record": True,
            "scientific_document_v1": True,
            "inline_property_slots": True,
            "sample_record_history": True,
            "sample_batch_create": True,
            "record_table_query": True,
            "experiment_references": True,
            "experiment_reference_commands": True,
            "process_definition_versions": True,
            "process_execution_bindings": True,
            "data_representations": True,
            "recoverable_data_drafts": True,
            "views": True,
            "pinned_view_manifests": True,
            "claims": True,
            "pinned_claim_sources": True,
            "claim_context_reverse_lookup": True,
            "assets": True,
            "change_sets": True,
            "idempotency": True,
            "optimistic_concurrency": True,
        },
        # Keep the boolean feature map for existing clients while exposing
        # the evidence state used by UI/MCP entry gates.
        "feature_status": {
            "scientific_document_v1": {
                "contract": True,
                "experimental": False,
                "accepted": True,
            },
            "inline_property_slots": {
                "contract": True,
                "experimental": True,
                "accepted": False,
            },
            "record_table_query": {
                "contract": True,
                "experimental": False,
                "accepted": False,
            },
            "recoverable_data_drafts": {
                "contract": True,
                "experimental": False,
                "accepted": False,
            },
            "pinned_view_manifests": {
                "contract": True,
                "experimental": False,
                "accepted": False,
            },
            "pinned_claim_sources": {
                "contract": True,
                "experimental": False,
                "accepted": False,
            },
        },
        "write_entrypoints": {
            "sample_record": "enabled",
            "data_draft": "enabled",
            "view": "enabled",
            "claim": "enabled",
            "physical_delete": "restricted",
        },
        "write_policy": {"external_agent_default": "proposal", "unit_conversion": False},
    }
