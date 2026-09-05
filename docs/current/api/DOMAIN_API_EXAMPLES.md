# v0.3 API Examples

Create a tagged Research Object:

```http
POST /api/v1/objects
Content-Type: application/json

{"kind":"research_object","title":"Batch A","tags":["样品","原料"]}
```

Create a Data representation:

```http
POST /api/v1/data/<data-id>/representations
Content-Type: application/json

{"kind":"table","name":"measurement table","format":"json","inline_payload_jsonb":{"rows":[]}}
```

Create an Experiment reference record:

```json
{
  "project_scope_id": "<project-id>",
  "experiment": {"title": "Run context", "status": "draft"},
  "references": [
    {"target_id": "<data-id>", "target_kind": "data", "role": "measurement"}
  ]
}
```

Aggregate responses include `record_sha256`; conditional updates use `If-Match`, and retryable creates may send `Idempotency-Key`.
