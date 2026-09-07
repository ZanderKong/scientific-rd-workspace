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
