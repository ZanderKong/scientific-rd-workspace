# Capabilities and Schemas v0.3

`GET /api/v1/capabilities` is the discovery source for the active contract.

```json
{
  "api_contract_version": "0.3",
  "object_kinds": ["research_object", "process_definition", "data", "experiment", "project", "view", "claim"],
  "relation_types": ["references", "subject", "derived_from", "related_to"],
  "representation_kinds": ["raw_file", "table", "image", "description", "structured"]
}
```

Material, Equipment and Sample are tags on `research_object`. Process definitions and executions have separate DTOs. Data representations are immutable and content-addressed; View and Claim records expose revisions. Pydantic schemas in `api/app/schemas.py` are the REST source of truth, and MCP uses the same services.
