# GitHub Handoff

## Current status — 2026-09-04

Scientific R&D Workspace is on the v0.2 canonical Research Object Graph architecture.

Current runtime facts:

- PostgreSQL 17 is the only supported database.
- `ResearchObject` and typed `ObjectRelation` are the canonical scientific domain model.
- Sample Record, Experiment Record, Experiment Comparison, Scientific Data, Planned/As-run Execution and ChangeSet are active domain services.
- REST API and MCP reuse the same backend domain services and semantic validation.
- External agents do not embed a second scientific runtime; existing-record mutations default to proposal-first ChangeSets.
- The active comparison implementation is `ExperimentComparisonService` with `/experiments/{id}/comparison`.
- The old phase-specific AI Analysis, generic Compare, Literature, Evidence and Evaluation runtimes are removed from the active product.

## Source of truth

Read these files for current behaviour:

1. `README.md`
2. `docs/PRODUCT_SPEC.md`
3. `ARCHITECTURE.md`
4. `docs/DATA_MODEL.md`
5. `docs/UI_SPEC.md`
6. `docs/api/DOMAIN_API.md`
7. `docs/agent/AGENT_INTERFACE.md`

`docs/exec-plans/` records how the repository evolved. It is historical engineering material and must not override the current source-of-truth documents.

## Current local setup

```bash
docker compose up -d postgres

cd api
uv sync --frozen
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

cd ../web
npm ci
npm run dev
```

The workspace must fail explicitly when PostgreSQL is unavailable. There is no SQLite fallback.

## Current verification surface

```bash
cd api
uv run ruff check app tests alembic/versions
uv run ruff format --check app tests alembic/versions
uv run pytest -q

cd ../web
npm run lint
npm run format:check
npm run typecheck
npm test -- --run
npm run build
```

CI also validates PostgreSQL migrations, migration/model parity, repeat-safe seed, browser workflows and MCP protocol behaviour.

## Historical boundary

Earlier Phase 1–3 handoffs, SQLite-era functional audits and screenshots of removed AI/Literature/Evidence/Evaluation/generic Compare surfaces are not current product documentation. Git history remains the source for those historical artefacts.
