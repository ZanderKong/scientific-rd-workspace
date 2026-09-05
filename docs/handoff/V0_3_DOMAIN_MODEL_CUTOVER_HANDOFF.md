# v0.3 Domain Model Cutover — Handoff

## 1. Baseline

- Baseline SHA: `a960d9b6a601838164bc05317e9b7807f5d19f49`
- Working branch: `feat/plan10-workspace-shell-resource-settings`
- Final commit SHA: not created; this handoff describes the current uncommitted working tree so pre-existing Plan 10 changes remain attributable.

## 2. Domain result

- Canonical kinds are `research_object`, `process_definition`, `data`, `experiment`, `project`, `view`, and `claim`.
- Material, Equipment and Sample are Research Object tags.
- Process Definitions are versioned templates; Process Executions pin versions and support multiple object/data bindings, field snapshots, outputs and revisions.
- Experiment is reference-only. Data supports multiple representations, origin, Assets and system-managed `subject` / `derived_from` shortcuts. View and Claim services are active.

## 3. Migrations

- `0007_v0_3_canonical_tables.py`: transitional v0.3 tables, tags/process fields and renamed legacy tables.
- `0008_v0_3_data_migration.py`: objects, relations, assets, representations, imports, definitions/executions and legacy SampleExecution audit migration.
- `0009_v0_3_remove_legacy_runtime.py`: removes legacy storage names and usage schema.
- `0010_v0_3_integrity_and_indexes.py`: strict v0.3 checks and query indexes.
- `0001`–`0006` were not modified.

## 4. Removed runtime and API

Removed active legacy service modules: composition, old SampleExecution and ExperimentComparison. Old payload/composition/comparison/execution endpoints are absent. REST and MCP use the v0.3 services and DTOs; MCP writes remain proposal-first.

## 5. Frontend

`web/src/lib/domain.ts` and `web/src/lib/api-client.ts` now expose v0.3 types and paths only. Sample pages use Process Execution projections, Experiment pages show references, Data pages show representations and lineage, and generic creation uses `research_object` plus tags. The existing shell/setting work was preserved; this cutover did not perform a final visual redesign.

## 6. Verification

Executed locally:

- Fresh PostgreSQL: `alembic upgrade head` and repeat-safe `python -m app.seed`.
- Legacy-shaped PostgreSQL: `0001` → `0006`, inserted v0.2-shaped objects/relations/payload/attachment/sample execution, then `0007` → `0010`; migrated objects, representation, Asset, Process Execution and strict v0.3 relation kinds verified; legacy table removed.
- Backend: isolated PostgreSQL `uv run pytest -q` — 10 passed after storage coverage was added.
- Frontend: `npm run typecheck` — passed; `npm test -- --run` — 11 tests passed.

The frontend production build passed. A local Next production HTTP smoke also returned 200 for `/`, `/dashboard/processes`, `/dashboard/views`, and `/dashboard/claims`. CI and an interactive browser session were not run in this local turn and remain release gates.

## 7. Known limitations / deviations

- The legacy migration can only synthesize a migrated SampleExecution when at least one Process Definition exists; ambiguous legacy records are not guessed into a new scientific Process Definition.
- S3 is implemented as an injectable optional provider and covered by a fake-client test; no live S3 credentials are required.
- The API router remains a single module for now; typed v0.3 paths and services are implemented without a router split.
- Final UI visual design and richer View/Claim editors remain follow-up work; the local HTTP smoke passed, but no interactive browser session was run.
