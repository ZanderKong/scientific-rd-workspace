# Sample Recording API Examples v0.3

```json
{
  "project_scope_id": "<project-id>",
  "sample": {"title": "Sample A", "tags": ["样品", "原料"]},
  "steps": [{
    "process_definition_id": "<definition-id>",
    "process_definition_version_id": "<version-id>",
    "object_bindings": [{
      "research_object_id": "<object-id>",
      "direction": "input",
      "role": "source",
      "values": {"amount": {"value": 10, "unit": "g"}}
    }],
    "data_bindings": []
  }]
}
```

Submit this once to `POST /api/v1/sample-records`. The response contains Process Execution projections, pinned versions and binding snapshots. Historical binding values remain stable when the Research Object or Definition changes.
