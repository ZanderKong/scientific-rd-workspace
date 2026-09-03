# v0.2 Research Object Graph Core — Handoff

## Delivered

The v0.2 clean cutover is implemented around `ResearchObject`, `ObjectRelation`, immutable `ObjectTypeVersion`, `ObjectRevision`, object-centric `Attachment`, `DataImport`, `DataPayload` and `DataPoint`.

The active API is under `/api/v1` and the active web shell exposes Overview, Projects, Experiments, Samples, Processes, Data, Materials and Equipment. Sample and Experiment context endpoints use bounded graph traversal. The seed creates a repeat-safe synthetic/anonymised chlorine response graph with a downstream branch and XY payload provenance.

## Removed/deferred

The old Project/Experiment/Measurement domain routers, AI runtime, Compare, Literature, Evidence and Evaluation active surfaces are removed from the v0.2 runtime. Their history remains available in Git history and the `v0.1-demo` tag; reintroduction requires Plan 2.

## Verification record

Passed locally:

- backend model import and SQLAlchemy mapper configuration;
- backend Ruff check and format check;
- frontend Oxlint (existing warnings remain in untouched calendar/info-button components), TypeScript typecheck, Oxfmt check and Vitest.

Not available on this host:

- live PostgreSQL migration/seed/API tests, because no local PostgreSQL service or Docker runtime is installed;
- production browser smoke against a running API.

The PostgreSQL-only fixture intentionally fails rather than falling back to SQLite. `.github/workflows/v0.2-core-ci.yml` is the formal PostgreSQL gate and must be green before declaring the final Plan 07 verdict.

## Runbook

```bash
docker compose up -d db
cd api
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.seed
uv run python -m app.seed
uv run pytest -q
cd ../web
npm ci
npm run lint
npm run typecheck
npm test -- --run
npm run build
```
