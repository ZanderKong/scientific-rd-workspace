# Sample Recording v1.5

Sample recording is one Scientific Record aggregate: a tagged `research_object`, a versioned `ScientificDocumentV1`, stable occurrences, authored Process Executions and object bindings.

```text
GET  /api/v1/samples/{id}/record
GET  /api/v1/samples/{id}/record/revisions/{revision_number}
POST /api/v1/sample-records
POST /api/v1/sample-records/batch
PUT  /api/v1/samples/{id}/record
```

The document contains atomic `processRef` and `objectRef` inline nodes whose `occurrenceId` values address the typed `occurrences` array. Process values belong to the occurrence's authored Execution; a bound object's usage values belong to its stable binding; an unbound object's local values remain in the document occurrence. Process Definition versions, object revisions, field snapshots and identities are pinned when saved.

Create and batch requests require `Idempotency-Key`. Updates require `base_record_sha256`; stale writes return a conflict without replacing the client draft. Document-managed Executions cannot be changed through the standalone Execution endpoint. A save writes the document, occurrences, executions, bindings, projections and revision manifest in one transaction.
