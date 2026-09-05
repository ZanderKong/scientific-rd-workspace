# v0.3 Domain Correctness & Test Foundation Handoff

Plan: 10.1 — v0.3 Domain Correctness & Test Foundation  
Repository: `ZanderKong/scientific-rd-workspace`  
Branch: `feat/plan10-workspace-shell-resource-settings`  
Baseline: `f99499c feat: complete v0.3 domain model cutover`  
Implementation commit: `94e7cc2 fix: enforce v0.3 domain correctness invariants`  
Plan 10.2: deferred

## What changed

- Provenance is execution-binding authoritative. `subject` and `derived_from` are materialized system shortcuts only; generic relation create/update/delete rejects those relation types.
- Process Execution validates canonical binding kinds, project scope, one Data output producer, Sample Record membership, explicit precedence scope and DAG cycles.
- Sample Record create/update is one transaction and preserves supplied `execution_id` identities while rebuilding the ordered execution DAG.
- Process Definition versions, object/data/view/claim/process revisions and Data Representations are append-only/immutable. Generic Research Object writes now create ObjectRevision rows.
- Data Representation lineage rejects cycles; Data records retain an origin representation and revision snapshot.
- Process Executions can pin a View and an exact View revision.
- Asset upload streams through a temporary file, verifies size and SHA-256, uses opaque keys, and blocks deletion while referenced.
- ChangeSet create/apply now records created target identity; update results return a newly computed aggregate hash; unsupported Process Definition updates are removed from the proposal contract.
- The Sample Composer supports multiple ordered steps, dynamic definition fields, version selection, step identity preservation, `/` Process Definition resolution and `@` object/tag resolution.

## Migration notes

- `0007_v0_3_canonical_tables` now uses explicit Alembic DDL rather than `Base.metadata.create_all`.
- `0011_v0_3_provenance_pins` adds `source_view_id` and `source_view_revision_id` to Process Execution.
- `0012_v0_3_schema_alignment` aligns metadata indexes/constraints with explicit migrations.
- A real PostgreSQL 0006-to-head fixture was exercised with legacy process, material, data, sample, relations and SampleExecution rows. Legacy process values and binding values were preserved, and legacy tables were removed at 0009.
- PostgreSQL remains mandatory for runtime and tests. SQLite fallback was not added.

## Verification

From `api/`:

```text
TEST_DATABASE_URL=postgresql+psycopg://.../scientific_rd_test_plan10_1 uv run pytest -q
17 passed
uv run ruff check app tests alembic/versions
DATABASE_URL=postgresql+psycopg://.../scientific_rd_migration_plan10_1c uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://.../scientific_rd_migration_plan10_1c uv run alembic check
No new upgrade operations detected.
```

From `web/`:

```text
npm run typecheck
npm run lint
npm test
12 tests passed
npm run build
```

`npm run format:check` still reports formatting differences in unrelated pre-existing workspace files; all Plan 10.1 touched frontend files were formatted and checked.

## Follow-up / known limits

- Browser-level REST/MCP/CI acceptance remains Plan 10.2 scope.
- Alembic autogenerate emits an existing SQLAlchemy warning about mutually dependent Claim/View revision tables; `alembic check` still reports no drift.
- Physical asset cleanup is best-effort after the database row is deleted; failures are logged for operational reconciliation.
