# Domain API Examples

Examples use UUID placeholders and `/api/v1` as the base path.

## Create an Experiment with reusable Samples

```http
POST /experiment-records
Idempotency-Key: experiment-import-2026-09-04-01
Content-Type: application/json

{
  "project_scope_id": "<project-id>",
  "experiment": {"title": "Temperature comparison", "status": "planned"},
  "members": [
    {"sample_id": "<sample-a-id>", "note": "baseline"},
    {"sample_id": "<sample-b-id>", "note": "high temperature"}
  ]
}
```

The response contains an Experiment Record and `ETag: "<record_sha256>"`. Membership is `includes`; the Samples' existing `contains` ownership is unchanged.

## Update a Sample Record safely

```http
PUT /samples/<sample-id>/record
If-Match: "<record_sha256>"
Content-Type: application/json

{
  "sample": {"title": "Baseline, as-run"},
  "steps": [/* complete desired-state process steps */],
  "change_note": "Record actual run"
}
```

If another client changed the record, the response is `412` with `error.code = stale_record`.

## Create typed Data

Scalar:

```http
POST /data/<data-id>/payloads/scalar
Content-Type: application/json

{"name":"Response time","value":8.3,"unit":"s"}
```

Table:

```http
POST /data/<data-id>/payloads/table
Content-Type: application/json

{
  "name": "Calibration table",
  "columns": [
    {"key":"concentration","label":"Concentration","value_type":"number","unit":"ppm"},
    {"key":"response","label":"Response","value_type":"number","unit":"%"}
  ],
  "rows": [
    {"values":{"concentration":10,"response":0.31}},
    {"values":{"concentration":20,"response":0.52}}
  ]
}
```

File payloads require an existing `source_attachment_id`; they do not fabricate parsed values. CSV/XLSX import can commit explicitly as either `xy_series` or `table`.

## Planned → As-run execution

```http
POST /samples/<sample-id>/execution/start
Idempotency-Key: execution-start-<sample-id>

PUT /samples/<sample-id>/execution
Content-Type: application/json

{"observations":[{"text":"Color developed at 85 C"}],"deviation_notes":[{"text":"Oven ran 5 C high"}]}
```

`GET /samples/<sample-id>/execution` returns the frozen `planned` record, current `as_run`, and deterministic `diff`. Complete or cancel is explicit and history is retained.

## Proposal-first external write

```http
POST /change-sets/propose
Content-Type: application/json

{
  "operation_kind": "update_sample_record",
  "project_scope_id": "<project-id>",
  "target_id": "<sample-id>",
  "base_record_sha256": "<record_sha256>",
  "request_payload_jsonb": {"sample": {"title":"Reviewed title"}, "steps": []},
  "source_client_name": "external-agent",
  "source_transport": "rest"
}
```

A proposal creates no authoritative scientific mutation. A reviewer approves, edits, or rejects it through `/change-sets/{id}/review`; approval rechecks the base hash and applies through the canonical domain service.
