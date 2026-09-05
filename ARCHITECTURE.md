# Architecture

Scientific R&D Workspace v0.3 keeps one canonical domain implementation behind the Web UI, REST API and MCP adapter.

```text
Next.js UI ───────────┐
REST /api/v1 ─────────┼──> FastAPI domain services ───> PostgreSQL 17
MCP adapter ──────────┘             │
                                   ├── revisions / hashes / ETags
                                   ├── ChangeSet / idempotency
                                   └── Local or optional S3 assets
```

## Canonical domain

- `ResearchObject` is the unified physical object. Material, Equipment and Sample are tags, not kinds.
- Kinds are `research_object`, `process_definition`, `data`, `experiment`, `project`, `view` and `claim`.
- `ProcessDefinition` owns versioned templates. `ProcessExecution` pins one version and stores many object/data bindings, field snapshots and execution revisions.
- `Experiment` is a non-owning reference context. It never owns scientific provenance or execution state.
- `DataRecord` owns multiple immutable `DataRepresentation` rows, an optional origin representation and system-managed `subject` / `derived_from` edges.
- `View` references Data without copying values. Process Executions that consume a View persist both `source_view_id` and `source_view_revision_id`. `Claim` stores a statement, source/confidence and ordered evidence with scope and cycle checks.
- `Asset` stores file metadata; bytes go through `StorageProvider` with Local as the default and optional S3-compatible routing.

## Service boundaries

`api/app/services.py` owns Research Object and generic relation invariants. `process_definition_service.py`, `process_execution_service.py`, `data_service.py`, `experiment_record_service.py`, `view_service.py`, `claim_service.py` and `project_context_service.py` expose typed aggregate operations. `sample_record_service.py` is a product projection over Process Executions, not a second persistence model.

Web and MCP call these services through typed DTOs. MCP writes are proposal-first ChangeSets; it does not implement a second mutation path or embed an LLM.

## Active API

The active router remains `/api/v1` and exposes typed v0.3 paths:

- `/objects`, `/relations`, `/object-types`, revisions and `/capabilities`;
- `/process-definitions*` and `/process-executions*`;
- `/sample-records`, `/samples/{id}/record`, context and lineage;
- `/experiment-records`, `/experiments/{id}/record`;
- `/data-records`, `/data/{id}/record`, `/data/{id}/representations` and imports;
- `/views*`, `/claims*`, object assets, project records/context/search and ChangeSets.

Old payload, composition, comparison and SampleExecution endpoints are not active runtime.

## Persistence and migration

PostgreSQL is mandatory. Alembic revisions `0001`–`0006` remain unchanged. Revisions `0007`–`0012` migrate the old storage shape to v0.3, remove legacy tables/runtime names, persist View provenance pins and align explicit migration indexes/constraints. Fresh database upgrade and an isolated 0006-to-head upgrade are release gates.

No SQLite fallback, queue, React Flow, second global state store, or final visual redesign is part of this cutover.
