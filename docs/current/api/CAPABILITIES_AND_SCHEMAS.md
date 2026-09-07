# Capabilities and Schemas v1.5

`GET /api/v1/capabilities` is the discovery source for the active contract.

```json
{
  "api_contract_version": "1.5",
  "object_kinds": ["research_object", "process_definition", "data", "experiment", "project", "view", "claim"],
  "relation_types": ["references", "subject", "derived_from", "related_to"],
  "representation_kinds": ["raw_file", "table", "image", "description", "structured"],
  "features": {
    "scientific_document_v1": true,
    "inline_property_slots": true,
    "sample_batch_create": true,
    "record_table_query": true,
    "recoverable_data_drafts": true,
    "pinned_view_manifests": true,
    "pinned_claim_sources": true
  }
}
```

Material, Equipment and Sample are tags on `research_object`. The boolean feature map is retained for discovery compatibility. `feature_status` distinguishes a contract that exists from an experimental surface and an acceptance gate that has actually passed; UI and MCP entry points should use that status instead of treating every contract as released. `write_entrypoints.physical_delete` is `restricted` while historical impact checks remain in force. Pydantic schemas in `api/app/schemas.py` are the REST source of truth, and MCP uses the same services and v1.5 write contracts.
