# Architecture — v0.2 Research Object Graph

## System shape

```text
Next.js App Router
       │ typed REST /api/v1
       ▼
FastAPI object-graph router
       │ domain services + GraphQueryService
       ├── PostgreSQL (canonical objects, relations, revisions, payload metadata)
       └── LocalStorageAdapter (attachment bytes)
```

PostgreSQL is mandatory. `api/app/db.py` rejects non-PostgreSQL URLs, the Alembic history is a fresh v0.2 baseline, and tests require `TEST_DATABASE_URL` or the configured PostgreSQL URL.

## Canonical backend

- `ResearchObject` is the only domain record for material, sample, equipment, process, data, experiment and project.
- `ObjectType` plus immutable `ObjectTypeVersion` supplies JSON Schema and UI metadata.
- `ObjectRelation` is the typed graph edge. Service validation enforces scope, allowed source/target kinds, no self-edge, valid quantity metadata and semantic uniqueness.
- `ObjectRevision` stores an immutable JSONB snapshot and SHA-256 digest. Revision numbers are allocated under a row lock.
- `Attachment` stores object-centric provenance metadata; bytes remain outside PostgreSQL.
- `DataImport` preserves source checksum, parser version, mapping, warnings and errors. `DataPayload` and `DataPoint` store validated immutable XY values without interpolation or unit conversion.
- `GraphQueryService` owns direct provenance and bounded upstream/downstream traversal. Default depth is 3, maximum depth is 8, and visited-node guards prevent cycles.

## API surface

The active router is `api/app/routers/objects.py` under `/api/v1`:

- `/object-types`
- `/objects` and `/objects/{id}`
- `/relations`
- `/objects/{id}/revisions`
- `/objects/{id}/attachments` and `/attachments/{id}`
- `/samples/{id}/context` and `/experiments/{id}/context`
- `/data/{id}/imports`, `/data/{id}/payloads` and `/data-payloads/{id}`

The old project/experiment/measurement/AI/literature/evaluation routers are not active runtime.

## Frontend shape

`web/src/features/workspace/components/workspace-app.tsx` is the v0.2 object-centric surface. It provides one shared list/detail/editor/composer implementation for all seven kinds, with route-specific pages only selecting the kind. The shell provides Project/Vault scope switching and navigation for Overview, Experiments, Samples, Processes, Data, Materials and Equipment.

The structured process composer is keyboard-first: `@` reference search, arrow selection, Enter selection, Tab traversal, Escape close and Cmd/Ctrl+Enter save. Context pages keep direct provenance, upstream/downstream lineage and current data visibly separate.

## Non-goals

No React Flow, SQLite fallback, new queue, second database, full form engine, multiplayer/RBAC, instrument integration, inventory ERP, or restored Plan 2 AI/Compare/Evidence/Evaluation/Literature runtime.
