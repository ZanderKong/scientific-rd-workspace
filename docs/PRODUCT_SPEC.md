# Product Spec — v0.2 Research Object Graph

Scientific R&D Workspace is a project-scoped research workbench for recording experimental work as a traceable object graph. The product goal of this cutover is a small, reliable core: researchers can create objects, connect them with meaningful relations, inspect provenance, revise records, and attach/import scientific data.

## Canonical language

The domain has exactly seven kinds:

`material` · `sample` · `equipment` · `process` · `data` · `experiment` · `project`

Relations are limited to:

`contains` · `includes` · `uses` · `produces` · `precedes` · `related_to`

The backend is the semantic authority. A relation is rejected when its source/target kinds, project scope, role, quantity, or uniqueness are invalid.

## Primary journey

```text
Project / Vault
  → Sample Record
  → Process Blocks
  → Material + Equipment + Sample
  → current Data
  → direct provenance and bounded lineage
  → revision snapshot
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

AI generation, Evidence, Evaluation, Literature, free-form graphs and Equipment Type inheritance remain separate follow-up work. External agents are not embedded in the workspace; mutations are validated by the domain services and proposal-first ChangeSets must not be simulated with `related_to` or exclusive `contains` ownership.

## Quality bar

Fresh PostgreSQL migration, repeat-safe seed, explicit typed API contracts, no SQLite fallback, no silent data conversion, visible error/loading/empty states, passing frontend checks, and green PostgreSQL CI are required for acceptance.
