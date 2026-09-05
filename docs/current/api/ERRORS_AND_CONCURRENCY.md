# Errors, Concurrency and Idempotency

Domain errors use this envelope:

```json
{
  "detail": {
    "error": {
      "code": "stale_record",
      "message": "The record changed after it was loaded.",
      "path": null,
      "details": {},
      "request_id": "..."
    }
  }
}
```

Typical status mapping is 404 for missing objects, 409 for semantic or database conflicts, 412 for a stale `If-Match`, and 422 for invalid domain input. Import diagnostics additionally preserve row/column locations.

The client should read an aggregate, retain `record_sha256`, then send `If-Match: "<hash>"` on updates. A stale update must be re-read and reconciled; the server never silently merges scientific records.

For retryable create/start/complete operations, send a stable `Idempotency-Key`. Idempotency records persist in PostgreSQL and include the request hash, response body and status. Reusing a key with a different request is a conflict.
