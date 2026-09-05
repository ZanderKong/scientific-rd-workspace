# Plan 08 交接：Sample-first Recording Workflow

## 状态

**PLAN 08 PASS — SAMPLE-FIRST RECORDING WORKFLOW READY**

Implementation commit verified by CI: `0c5c0820bc1d429035a3c6ac6f88c165c6c5b0da`.
The closeout documentation is on `origin/main` after that implementation.

## 已交付范围

- Sample-first composer: every new record starts with one Process Block and no raw JSON editing is required.
- `/` Process command palette with keyboard selection and existing Process definition reuse.
- `@` resolver for Material, Equipment, and optional precursor Sample references, with keyboard navigation and a two-pane desktop preview.
- Schema-driven inline Material/Equipment draft creation. Identity fields come from the active object-type schema; the typed query pre-fills the title, while identity remains distinct from use values.
- Grouped resolver results and compact semantic resource tokens: Material amber, Equipment sky, precursor Sample violet. The token strip contains no category headings.
- Per-resource usage fields, including custom additions, stored on the concrete Process relation; Process parameters stay on the Process object.
- Atomic Sample Record create/update transaction: ordered Process steps, resource relations, revisions, and final `produces → Sample` provenance.
- Clean record-style Sample detail, shared Composer edit mode, and `基于此样品新建` clone flow. Clone creates new Sample/Process identities while reusing referenced Material/Equipment identities and use values.
- Regression-safe handling of legacy graph semantics: no automatic intermediate Sample creation, no Equipment Type hierarchy, and no destructive flattening of non-linear legacy graphs.
- Agent-facing contract and examples for desired-state updates, precursor Samples, Equipment usage schema additions, and usage values. The active examples are in [`docs/current/agent/SAMPLE_RECORDING_API_EXAMPLES.md`](../../current/agent/SAMPLE_RECORDING_API_EXAMPLES.md).

## 数据库迁移

- `api/alembic/versions/0003_sample_recording_workflow.py`
- Adds non-null `research_objects.usage_schema_jsonb` with an empty JSON object default.
- Existing migrations `0001` and `0002` remain unchanged. PostgreSQL 17 migration and parity checks pass in CI.

## API surface

The canonical aggregate contract is documented in [SAMPLE_RECORDING_API_EXAMPLES.md](../../current/agent/SAMPLE_RECORDING_API_EXAMPLES.md).

- `GET /api/v1/object-types` — schema/type definitions used by Process and resource command surfaces.
- `GET /api/v1/objects` — scoped object search; supports `kind`, repeated `kinds`, `project_scope_id`, `q`, `include_global`, and bounded limits.
- `POST /api/v1/sample-records` — atomic Sample-first create with ordered Process drafts, resource references or inline resource drafts, relation usage values, and schema additions.
- `GET /api/v1/samples/{sample_id}/record` — record projection for detail/edit/clone.
- `PUT /api/v1/samples/{sample_id}/record` — desired-state update with revision/provenance handling.
- Existing generic object, relation, revision, attachment, context, and composition endpoints remain available and retain Plan 07.1 semantics.

## 验证

### Local checks

- `cd web && npm run format:check` — pass.
- `cd web && npm run lint` — pass; only existing non-blocking warnings in starter UI components and one effect dependency.
- `cd web && npm run typecheck` — pass.
- `cd web && npm test -- --run` — pass: 3 files, 19 tests.
- `cd web && npm run build` — pass.
- `cd api && uv run ruff check app tests alembic/versions` — pass.
- `cd api && uv run ruff format --check app tests alembic/versions` — pass.

The local host has no Docker/PostgreSQL service, so database execution was not substituted with SQLite. The PostgreSQL gates below are the authoritative database evidence.

### GitHub CI

- Workflow: [Scientific Workspace CI](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33766298541)
- Run `33766298541` on implementation commit `0c5c082` — **success**.
- Backend/PostgreSQL 17: migration, model parity, repeat-safe seed, lint/format, benchmark smoke, and API tests all pass.
- Frontend: lint, format, typecheck, Vitest, and production build all pass.
- Browser/Sample Record acceptance: pass.

Browser evidence is retained in artifact [plan08-browser-acceptance](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33766298541/artifacts/9897802668), including 1440px and 1024px screenshots, snapshots for each workflow milestone, and `browser-acceptance.txt`.

The acceptance run created a source Sample and a clone, then verified through the API that Material and Equipment IDs were reused while Sample and Process IDs differed and the source title/record remained unchanged.

## Known limitations and deferred scope

- No embedded AI chat, OCR/handwriting ingestion, AI scientific diff, manual export, inventory/ERP, instrument control, multiplayer/RBAC, or generic workflow/template editor is included.
- Literature, Evidence Gate, Evaluation, and non-owning Experiment membership remain outside Plan 08.
- Automatic unit conversion and automatic intermediate Sample creation are intentionally not implemented.
- Inline resource creation creates a draft resource as part of the same Sample Record transaction; it does not introduce an independent Material/Equipment management application.
- Browser evidence is deterministic synthetic data from the seeded chlorine project (`PRJ-001`); production identity/authentication and deployment configuration remain environment concerns.

## Handoff notes

Continue from `origin/main`. The next product plan should preserve the established ownership rule: a Process owns its own parameters, a Process relation owns the concrete resource-use values, and a Sample Record update is the aggregate transaction boundary.
