# Product Spec — v0.2 Research Object Graph

Scientific R&D Workspace is a project-scoped research workbench for recording experimental work as a traceable object graph. The product goal of this cutover is a small, reliable core: researchers can create objects, connect them with meaningful relations, inspect provenance, revise records, and attach/import scientific data.

## Canonical language

The domain has exactly seven kinds:

`material` · `sample` · `equipment` · `process` · `data` · `experiment` · `project`

Relations are limited to:

`contains` · `uses` · `produces` · `precedes` · `related_to`

The backend is the semantic authority. A relation is rejected when its source/target kinds, project scope, role, quantity, or uniqueness are invalid.

## Primary journey

```text
Project / Vault
  → Experiment
  → Process
  → Material + Equipment + Sample
  → Data
  → direct provenance and bounded lineage
  → revision snapshot
```

The demo uses a synthetic/anonymised chlorine color-response material graph. It is illustrative only and must be labelled as synthetic in the UI and seed data.

## User-visible capabilities

- Switch the active Project/Vault scope from the shell.
- Browse and search object lists; create and edit typed objects with schema validation.
- Compose process inputs/outputs using `@` references and explicit relation metadata.
- Open Sample context with direct provenance, upstream/downstream samples, and current Data separated.
- Open Experiment context with contained samples/processes/data and derived materials/equipment.
- Upload CSV/XLSX, preview headers/rows, explicitly map X/Y columns, commit immutable XY points, and retain source checksum/parser/mapping provenance.
- Create and inspect append-only object revisions with snapshot hashes.

## Explicitly deferred

AI generation, Compare, Evidence, Evaluation and Literature are not active v0.2 features. They are Plan 2 work and must not remain as misleading active navigation or API runtime.

## Quality bar

Fresh PostgreSQL migration, repeat-safe seed, explicit typed API contracts, no SQLite fallback, no silent data conversion, visible error/loading/empty states, passing frontend checks, and green PostgreSQL CI are required for acceptance.
