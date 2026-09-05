# Plan 10 交接：Workspace Shell、Project、Equipment、Settings

> **历史交接记录**：本文记录 Plan 10 完成时的实现与证据边界；当前产品事实以 [`docs/handoff/CURRENT_STATE.md`](../../handoff/CURRENT_STATE.md) 为准。

## 状态

**PLAN 10 PASS — WORKSPACE SHELL / RESOURCE / SETTINGS READY**

Implementation is present on branch `feat/plan10-workspace-shell-resource-settings`, based on `main` at `a960d9b6a601838164bc05317e9b7807f5d19f49`. No commit was created in this execution.

## 已交付范围

- One client-side `ProjectScopeProvider` now owns project loading, route/query/localStorage/first-project resolution, scoped URL synchronization, stale-selection cleanup, creation, and browser-local avatar labels.
- The sidebar project switcher supports loading/error/empty/search/keyboard selection, first-project creation, Chinese/English labels, deterministic auto avatars, and validated custom labels.
- The primary navigation now exposes Experiments, Samples, Equipment, and Data. Existing deep links remain available.
- Sample and Experiment list surfaces consume the shared active project instead of maintaining separate project selectors. No-project states include direct creation CTAs.
- Equipment has dedicated list, new, detail, and edit routes. It supports global/current-project scope, identity fields, status, search/filtering, usage schema field creation/editing/reordering/deletion, select options, required/default-unit metadata, and unknown-property preservation.
- `/dashboard/data` is a deliberately read-only landing surface with project context and data count; Data detail/import/payload routes were not removed.
- A fixed bottom-right Settings trigger opens a hover/focus quick card and navigates on click to `/dashboard/settings`. Detailed settings cover locale, system/light/dark appearance, development-only React Query Devtools (off by default), and build/about metadata. The Header locale switcher was removed.
- All newly introduced shell, Project, Equipment, Data landing, and Settings copy is available in `zh-CN` and `en`.
- Browser first-run and seeded regression scripts/workflow coverage were added.

## Backend / data-model decision

No Alembic migration was added and canonical object kinds, relations, and API routes were preserved. A migrations-only database previously had no `ObjectType` catalog, which made the canonical Project Record endpoint fail on first use. The app now bootstraps only the canonical type catalog at startup, without creating synthetic research objects; the existing demo `seed` command reuses the same definitions.

The Equipment schema now includes the planned identity keys and permits extension metadata. When an existing immutable type version differs, the bootstrap creates a new active version rather than mutating the historical version.

## Key files

- `web/src/features/workspace/project-scope/` — project scope provider, switcher, creation, labels, avatar logic, storage contract.
- `web/src/features/equipment/` — Equipment management and usage-schema editor.
- `web/src/features/settings/` — Settings page, quick card, locale/theme/developer/about preferences.
- `web/src/features/data/data-landing.tsx` — deferred Data landing surface.
- `api/app/main.py`, `api/app/seed.py` — startup type-catalog bootstrap and schema-version handling.
- `.github/scripts/plan10-first-run-browser-smoke.sh` — no-seed browser acceptance.
- `.github/workflows/scientific-workspace-ci.yml` — independent PostgreSQL 17 Plan 10 browser job.

## Runtime

```bash
cd api
DATABASE_URL=postgresql+psycopg://scientific:scientific@localhost:5432/scientific_rd uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://scientific:scientific@localhost:5432/scientific_rd uv run uvicorn app.main:app --reload
```

```bash
cd web
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

The startup catalog is application metadata. Run `uv run python -m app.seed` only in a dedicated synthetic/demo database, before browser seeded regression; it is not part of first-run initialization.

## Verification results

- Frontend `npm run format:check` — pass.
- Frontend `npm run typecheck` — pass.
- Frontend `npm run lint` — pass with pre-existing non-blocking warnings in `sample-composer`, `calendar`, and `info-button`.
- Frontend `npm test -- --run` — pass, 6 files / 27 tests.
- Frontend `NEXT_PUBLIC_API_URL=... npm run build` — pass; routes include Equipment list/new/detail/edit, Data landing, and Settings.
- Backend `uv run ruff check app tests alembic/versions` — pass.
- Backend `uv run ruff format --check app tests alembic/versions` — pass.
- Backend `uv run pytest -q` — pass, 38 tests.
- Blank PostgreSQL 17 migration — pass through `0006_agent_changes`.
- Clean blank PostgreSQL 17 repeat-safe seed — pass: seed twice plus existing count/graph assertions.
- No-seed browser first-run — pass manually against a fresh migrations-only PostgreSQL 17 container: create project, create Sample, create Equipment, define `rpm`/`duration`, edit model, resolve Equipment from Sample, inspect read-only Data landing, focus Settings quick card, switch locale/theme, override/reset avatar.
- Seeded browser regression — pass manually after clean seed: Sample list shows 4 seeded records and the `SMP-001` detail renders its Process/resource/provenance/execution surface.
- `git diff --check` and both browser smoke scripts `bash -n` — pass.

## Known issues / intentional boundaries

- Data creation, import, visualization, and analysis remain intentionally deferred behind the read-only landing page.
- The existing synthetic seed uses fixed demo codes and is intended for a dedicated demo database. Running it after first-run user objects that reuse those codes can hit the existing graph scope protections; this is not a first-run path.
- Existing frontend lint warnings listed above remain outside Plan 10.
- Authentication, RBAC, multiplayer state, inventory/ERP integration, instrument control, and other product surfaces remain outside this plan.

## Handoff constraints

- Keep `ProjectScopeProvider` as the only shell-level active-project resolver; do not add page-local project selectors or duplicate localStorage keys.
- Keep project avatar labels and developer preferences browser-local; never write them into scientific objects.
- Preserve Equipment identity in `properties_jsonb` and per-resource actual usage values on Process relations. Do not flatten usage schema into historical usage records.
- Preserve existing Data deep-link and API routes while building the next Data surface.
- Treat object type versions as immutable; evolve schemas by adding a new version.

## Recommended next action

Use the shared Project/Data contracts to design the next Data Workspace increment, retaining the no-write landing behavior until the data record/import workflow is explicitly scoped.
