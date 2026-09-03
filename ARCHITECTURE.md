# Architecture — v0.2 Research Object Graph

## System shape

```text
Next.js App Router
       │ typed REST /api/v1
       ▼
FastAPI object-graph router
       │ domain services + GraphQueryService
       ├── PostgreSQL (canonical objects, relations, records, execution, revisions, payload metadata)
       └── LocalStorageAdapter (attachment bytes)

External agents use the same domain services through REST or the official MCP SDK adapter. MCP is an adapter layer, not a second mutation implementation; it has no embedded LLM.
```

PostgreSQL is mandatory. `api/app/db.py` rejects non-PostgreSQL URLs, the Alembic history is a fresh v0.2 baseline, and tests require `TEST_DATABASE_URL` or the configured PostgreSQL URL.

## Canonical backend

- `ResearchObject` is the only domain record for material, sample, equipment, process, data, experiment and project. Material and Equipment identity stays on the object; actual per-Process usage values stay on the `uses` relation.
- `ObjectType` plus immutable `ObjectTypeVersion` supplies JSON Schema and UI metadata.
- `ObjectRelation` is the typed graph edge. Centralized semantic validation enforces scope, allowed source/target kinds, role aliases, no self-edge, valid quantity metadata, one Experiment owner, one producer, and cycle-free precursor/precedes graphs. `related_to` is never used for canonical provenance.
- `ObjectRevision` stores an immutable JSONB snapshot and SHA-256 digest. Revision numbers are allocated under a row lock.
- `Attachment` stores object-centric provenance metadata; bytes remain outside PostgreSQL.
- `DataImport` preserves source checksum, parser version, mapping, warnings and errors. `DataPayload` and `DataPoint` store validated immutable XY values without interpolation or unit conversion.
- `ExperimentRecordService` models non-owning Experiment → Sample membership with `includes`; `ExperimentComparisonService` aligns process type/occurrence, resource identity and usage values deterministically. `ProjectContextService` provides bounded context and search.
- `DataPayload` supports scalar, XY series, explicit typed tables and file references. `SampleExecution` freezes a planned Sample Record at start and exposes an as-run diff. `IdempotencyRecord` and `ChangeSet` make retry/review behavior persistent.
- `GraphQueryService` owns direct provenance and bounded upstream/downstream traversal. Default depth is 3, maximum depth is 8, and visited-node guards prevent cycles. Only subject relations drive current Data; only precursor relations drive lineage. Process composition is reconciled as a single desired-state transaction. `SampleRecordService` projects a simple linear record from the final Sample's producing Process and atomically creates/edits its Process chain.

## API surface

The active router is `api/app/routers/objects.py` under `/api/v1`:

- `/object-types`
- `/objects` and `/objects/{id}`
- `/relations`
- `/objects/{id}/revisions`
- `/objects/{id}/attachments` and `/attachments/{id}`
- `/samples/{id}/context` and `/experiments/{id}/context`
- `/samples/{id}/record` and `/sample-records`
- `/processes/{id}/composition`
- `/projects/{id}/summary` and `/workspace/summary`
- `/project-records`, `/projects/{id}/record`, `/projects/{id}/context`, `/projects/{id}/search`
- `/experiment-records`, `/experiments/{id}/record`, `/experiments/{id}/comparison`
- `/data-records`, `/data/{id}/record`, typed `/data/{id}/payloads/*`
- `/samples/{id}/execution/*`, `/change-sets/*`, and `/capabilities`
- `/data/{id}/imports`, `/data/{id}/payloads` and `/data-payloads/{id}`

The old project/experiment/measurement/AI/literature/evaluation routers are not active runtime.

## Frontend shape

`web/src/features/workspace/domain-workspaces.tsx` provides dedicated Project, Experiment, Data and Sample Execution surfaces with typed summaries and tables. Samples retain the dedicated `web/src/features/workspace/sample-record/` feature: a shared create/edit Sample Composer, two-pane `@` resolver, resource tokens, dynamic usage fields, record detail, and Sample list. The shell keeps Project/Vault scope switching; generic routes remain available by URL.

The structured process composer is keyboard-first: `@` reference search, arrow selection, Enter selection, Tab traversal, Escape close and Cmd/Ctrl+Enter save. It submits one desired-state composition PUT; it does not loop over relation POSTs. Context pages keep direct provenance, upstream/downstream lineage and current data visibly separate, and render lineage as a backend-edge tree.

## Non-goals

No React Flow, SQLite fallback, new queue, second database, full form engine, multiplayer/RBAC, instrument integration, inventory ERP, or restored Plan 2 AI/Compare/Evidence/Evaluation/Literature runtime.
