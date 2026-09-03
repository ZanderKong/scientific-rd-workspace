# v0.2 Core Semantic Stabilization — Handoff

## Scope

Plan 07.1 stabilizes the v0.2 Research Object Graph on top of baseline commit `a78f49e`. The seven canonical object kinds remain unchanged. The new migration is `0002_v0_2_semantic_stabilization`.

## Delivered

- Central relation semantics with role alias normalization, role-required Process→Sample `uses`, scope checks, single ownership/producer cardinality, and precursor/precedes cycle detection.
- Default ObjectType selection with highest active version, immutable type identity/version schema fields, and PostgreSQL partial unique indexes.
- Role-aware Sample context: subject-only current Data, precursor-only lineage, direct `sample_inputs` with `relation_id`, and Experiment `input_samples` for cross-experiment reuse.
- Atomic Process composition GET/PUT with desired-state reconciliation, create-target XOR validation, and automatic ownership of new outputs.
- SQL-filtered object search, project/workspace summaries, preserved BlockNote JSON, real-X O(n) chart projection, and backend-edge lineage trees.
- Repeat-safe seed graph with eight processes, four samples, four data objects, preparation/measurement separation, and no redundant `related_to` provenance edges.
- Backend/API and frontend business tests plus CI seed assertions and benchmark smoke.

## Seed graph

`EXP-001` owns the baseline preparation/measurement; `EXP-002` owns the KI and branch processes plus `SMP-002`, `SMP-004`, `DAT-002`, `DAT-004`; `EXP-003` owns the KI+starch path plus `SMP-003` and `DAT-003`. `SMP-001` is the shared input to the two EXP-002 branches, and `SMP-002` is the input to the EXP-003 path.

## Verification

- Backend Ruff and format check: passed locally.
- Backend import/mapper check and Alembic offline `0001 → 0002`: passed locally.
- Frontend lint, typecheck, format, Vitest and production build: executed by CI; local unit/type gates are also run before handoff.
- PostgreSQL API tests and live migration/seed/benchmark require the CI PostgreSQL 17 service; this host has no local PostgreSQL/Docker service.
- Final commit: `e4a6c27e2b88b91cc6447dc8550b1590ef0ffae8`.
- Final green CI: [run 33728192210](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33728192210), including PostgreSQL 17 migration/parity, repeat-safe seed assertions, benchmark smoke, backend tests, and all frontend gates.

## Runbook

```bash
docker compose up -d postgres
cd api
uv run alembic upgrade head
uv run python -m app.seed
uv run python -m app.seed
uv run pytest -q
cd ../web
npm ci
npm run lint
npm run format:check
npm run typecheck
npm test -- --run
npm run build
```

## Final verdict

`PLAN 07.1 PASS — v0.2 CORE SEMANTICS STABILIZED`
