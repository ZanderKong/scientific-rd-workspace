# Sample Recording API Example v1.5

```json
{
  "project_scope_id": "<project-id>",
  "sample": {"title": "Sample A", "tags": ["样品", "原料"]},
  "document": {
    "schema_version": 1,
    "blocks": [{
      "type": "paragraph",
      "content": [{"type": "processRef", "props": {"occurrenceId": "<occurrence-id>"}}]
    }]
  },
  "occurrences": [{
    "occurrence_id": "<occurrence-id>",
    "kind": "process",
    "target_id": "<definition-id>",
    "process_definition_version_id": "<version-id>",
    "field_definitions": {"fields": [{"key": "temperature", "value_type": "number"}]},
    "values": {"temperature": {"value": 23.5, "unit": "°C"}},
    "status": "recorded"
  }]
}
```

Send this to `POST /api/v1/sample-records` with an `Idempotency-Key` header. The response returns the canonical document and occurrences, assigned Execution/binding IDs, `record_sha256`, Data links and edit blockers. Reuse the same key and payload to replay a lost successful response.

## AI-assisted entry loop

For an AI client, keep the scientific write loop reviewable and one record at a time:

1. Search the project-scoped object and process candidates with the normal list endpoints.
2. Build one typed Sample proposal using the selected IDs, version IDs and occurrence-local fields.
3. Submit it through the proposal/ChangeSet MCP flow, show the proposed title, refs and values for review, then apply it with an idempotency key.
4. Read the applied result back and retain its Sample ID, `record_sha256` and occurrence identity map.
5. Use the returned IDs as the context for the next record; never infer a new object or Process from a display name alone.

The human batch variable table remains a REST/UI workflow. AI clients should call the same single-record proposal and read-back loop repeatedly rather than inventing a second batch MCP contract.
