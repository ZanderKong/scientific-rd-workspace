# Product Specification

Scientific R&D Workspace 是一个 project-scoped 的实验研发工作台，围绕 Sample Record、Experiment Comparison、Scientific Data、Planned/As-run Execution 与可追溯 provenance 组织科研信息，并通过稳定的 domain services 向 Web UI、REST 和 MCP 提供一致能力。

## Canonical language

The domain has exactly seven kinds:

`material` · `sample` · `equipment` · `process` · `data` · `experiment` · `project`

Relations are limited to:

`contains` · `includes` · `uses` · `produces` · `precedes` · `related_to`

The backend is the semantic authority. A relation is rejected when its source/target kinds, project scope, role, quantity, or uniqueness are invalid.

## Primary journey

```text
Project
→ Sample Record
→ Process / Material / Equipment / precursor Sample
→ Planned / As-run Execution
→ Scientific Data
→ Experiment Comparison
→ Provenance / Revision
→ External Agent ChangeSet Review
```

The demo uses a synthetic/anonymised chlorine color-response material graph. It is illustrative only and must be labelled as synthetic in the UI and seed data.

## User-visible capabilities

- Switch the active Project/Vault scope from the shell.
- Browse and search object lists; create and edit typed objects with schema validation.
- Create and edit a Sample Record as one aggregate workflow. A record starts with one Process Block; `/` chooses a Process definition and `@` resolves resources.
- Store Material/Equipment identity on objects and actual use values on Process relations, with persisted per-resource usage-field definitions.
- Clone a Sample Record into a new draft with new Sample/Process IDs and reused resource identities.
- Compose process inputs/outputs using `@` references and explicit relation metadata.
- Open Sample context with direct provenance, upstream/downstream samples, and current Data separated.
- Open Experiment context with contained samples/processes/data and derived materials/equipment.
- Upload CSV/XLSX, preview headers/rows, explicitly map X/Y columns, commit immutable XY points, and retain source checksum/parser/mapping provenance.
- Create and inspect append-only object revisions with snapshot hashes.
- Group reusable Samples into Experiments with non-owning `includes` membership and deterministic comparison.
- Record Project context/search, typed scalar/XY/table/file Data payloads, and Planned → As-run Sample execution.
- Expose capabilities, ETags, persistent idempotency and proposal-first ChangeSets for external agents through REST and official MCP transports.

## Explicitly deferred

Embedded model runtimes, OCR/handwriting ingestion, literature retrieval, instrument control, inventory/ERP, automatic unit conversion, free-form graph editing and full multi-user RBAC remain outside the current product boundary.

## Quality bar

Fresh PostgreSQL migration, repeat-safe seed, explicit typed API contracts, no SQLite fallback, no silent data conversion, visible error/loading/empty states, passing frontend checks, and green PostgreSQL CI are required for acceptance.
