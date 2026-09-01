# Phase 2 — Scientific Workflow Handoff

## 1. Status

- **Implementation status:** complete in the working tree; PostgreSQL 17 acceptance is still pending in this environment.
- **Verdict:** `PHASE 2 NOT READY` until the PostgreSQL 17 CI/audit gates pass.
- **Phase 1 baseline:** `9bb494d` (Phase 1 remains frozen and passing).
- **Implementation commit:** `b916292` (`Implement Phase 2 scientific workflow`).
- **Scope boundary:** no Measurement Compare extensions beyond this plan, AI, LangGraph, Langfuse, MCP, embeddings, pgvector, Evidence Gate decisions, or other Phase 3 functionality were added.

## 2. Delivered slice

The Phase 2 workflow is now represented as:

`Raw Attachment → MeasurementImport → Measurement → Plot → Compare → Literature → Evidence`

Delivered components:

- First-class immutable `Measurement` and ordered `MeasurementPoint` entities owned by an Experiment.
- Explicit import provenance (`Attachment → MeasurementImport → Measurement`) with source checksum, parser metadata, mapping, validation errors, and row-level source references.
- Narrow, deterministic tabular import: UTF-8 CSV and XLSX, one worksheet, one numeric x column and one numeric y column per import. XLSX parsing is read-only and guarded by size/entry limits.
- Preview-before-commit import flow, explicit labels/units, controlled measurement types, line/scatter presentation, and immutable derived points.
- Attachment deletion protection for completed imports (`409 attachment_in_use`).
- Computed Experiment Compare with structured-property differences and compatible measurement overlays; no interpolation, resampling, or silent unit conversion.
- Manual/local Literature records, Experiment links, and human-authored Evidence with exactly one version-stable source (Literature, Measurement, or ExperimentRevision). Evidence can be withdrawn but is not edited in place or hard-deleted.
- Optional `LiteratureProvider` protocol seam; Zotero remains outside Phase 2 P0 and has no runtime dependency.
- Revision snapshot schema v2 for newly created revisions, preserving Phase 1 snapshot compatibility while including measurement, literature-link, and evidence references.
- Recharts-based Data and Compare views, Literature routes, experiment literature context, typed API-client support, and read-only revision reference rendering.
- PostgreSQL 17 GitHub Actions workflow covering migrations, seed idempotency, backend tests, frontend lint/typecheck/tests/format/build.

## 3. Schema and migration notes

Additive Alembic migrations:

- `0003_scientific_measurements`: `measurement_imports`, `measurements`, `measurement_points`.
- `0004_literature_evidence`: `literature_records`, `experiment_literature_links`, `evidence_records`.

Phase 1 guarantees remain intact:

- Experiments retain permanent binding to their exact immutable template version.
- Existing revision rows are append-only and are not rewritten; old snapshots continue to use `snapshot_json.experiment` and `snapshot_json.attachments`.
- New revision snapshots carry `snapshot_schema_version: 2` and optional Phase 2 references.
- Raw attachment bytes remain outside PostgreSQL; metadata remains authoritative in the database.

## 4. API and UI surface

New API routers:

- `POST /api/v1/experiments/{experiment_id}/measurement-imports/attachment`
- `POST|GET /api/v1/experiments/{experiment_id}/measurement-imports[/preview]`
- `GET /api/v1/measurement-imports/{import_id}` and `POST /api/v1/measurement-imports/{import_id}/commit`
- `GET /api/v1/experiments/{experiment_id}/measurements`
- `GET /api/v1/measurements/{measurement_id}[/points]`
- `POST /api/v1/comparisons/experiments`
- `GET|POST /api/v1/projects/{project_id}/literature`
- `GET|PATCH /api/v1/literature/{literature_id}`
- `GET|POST /api/v1/experiments/{experiment_id}/literature-links`
- `PATCH|DELETE /api/v1/experiment-literature-links/{link_id}`
- `GET|POST /api/v1/projects/{project_id}/evidence`
- `GET /api/v1/evidence/{evidence_id}` and `POST /api/v1/evidence/{evidence_id}/withdraw`

New or updated web surfaces:

- Experiment **Data** tab: import preview/mapping, provenance, summary statistics, table, and chart.
- `/dashboard/compare`: select 2–5 experiments from one project and compare structured properties and measurements.
- `/dashboard/literature`: create/edit/link local literature and manage evidence.
- Experiment literature context tab and read-only Phase 2 revision references.

## 5. Verification performed

| Gate | Result | Evidence |
| --- | --- | --- |
| Backend Ruff lint | PASS | `cd api && uv run ruff check app tests` |
| Backend format | PASS | `cd api && uv run ruff format --check app tests` |
| Backend tests | PASS | `cd api && uv run pytest` — 18 passed |
| Blank Alembic migration | PASS on SQLite fallback | `alembic upgrade head` through `0004` |
| Alembic parity | PASS on SQLite fallback | `alembic check` |
| Seed idempotency | PASS on SQLite fallback | seed twice; 3 measurements/imports, 1 literature, 1 evidence |
| Frontend lint | PASS | `cd web && npm run lint` (only inherited starter warnings) |
| Frontend format | PASS | `cd web && npm run format:check` |
| Frontend typecheck | PASS | `cd web && npm run typecheck` |
| Frontend tests | PASS | `cd web && npm run test` — 6 tests |
| Production build | PASS | `cd web && npm run build` |
| Local runtime smoke | PASS | API health/projects and web Compare route returned successfully |
| PostgreSQL 17 blank migration/seed/backend acceptance | **NOT RUN** | This host has no Docker, `psql`, or `pg_isready`; CI workflow is provided for the authoritative run |

The SQLite checks are development fallbacks only. They do not substitute for the required PostgreSQL 17 acceptance run.

## 6. Runbook for the authoritative audit

Prerequisites: Docker Desktop (or PostgreSQL 17), Node.js 22+, Python 3.11+, and `uv`.

```bash
cp api/.env.example api/.env
docker compose up -d postgres

cd api
uv sync --locked
uv run alembic upgrade head
uv run alembic check
uv run python -m app.seed
uv run python -m app.seed
uv run pytest
```

Run the frontend gates from `web`:

```bash
npm ci
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
```

GitHub Actions reproduces the PostgreSQL 17 service and these checks in `.github/workflows/phase-2-ci.yml`.

## 7. Deliberately deferred

- Zotero synchronization remains optional behind `LiteratureProvider`; manual Literature is the Phase 2 P0 path.
- Universal scientific file parsing, arbitrary schemas, unit conversion, interpolation/resampling, and instrument-specific adapters are out of scope.
- AI, RAG, embeddings, pgvector, LangGraph, Langfuse, MCP, automated findings, and Evidence Gate decisions remain Phase 3.

## 8. Handoff decision

The implementation is ready for review and CI execution. Do not label Phase 2 `PASS` until the PostgreSQL 17 gates above pass and this document is updated with that evidence.
