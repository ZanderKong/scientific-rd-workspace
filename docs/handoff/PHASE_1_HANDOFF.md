# Phase 1 — Foundation + ELN Core

## 1. Status

- PARTIAL — implementation and local checks pass. A Docker-free local SQLite deployment is now available; PostgreSQL-backed checks remain pending because Docker is unavailable in the current environment.
- Git commit/tag: `80dbf63` (Phase 1 implementation); local deployment additions are recorded in the next local commit.
- Date: 2026-09-01

## 2. What Was Actually Implemented

The repository now contains a Next.js 16/React 19 web workspace and a FastAPI/SQLAlchemy API for the Phase 1 path:

`Project → Experiment → Structured Properties → Rich Note → Attachments → Clone → Revisions`

Projects and experiments are editable through typed API calls. Experiment structured properties are validated against an active server-owned JSON Schema and rendered with JSON Forms. Notes are stored separately as BlockNote JSON. Attachments use a local storage adapter with safe keys, size enforcement, and SHA-256 metadata. Clone creates a new entity with parent lineage and a new initial revision. Revisions are immutable snapshots.

## 3. Repository Structure

- `web/` — Next.js app shell, workspace routes, JSON Forms, BlockNote, typed API client, Vitest tests.
- `api/` — FastAPI app, SQLAlchemy models, Alembic migration, seed, local storage adapter, API tests.
- `docker-compose.yml` — PostgreSQL 17 service.
- `data/uploads/` — local attachment storage root (ignored except placeholder).
- `third_party_licenses/` and `THIRD_PARTY_NOTICES.md` — direct reuse attribution.

## 4. Runtime

### Prerequisites

Node.js 22+, npm, Python 3.11+, uv, and Docker Desktop for PostgreSQL.

### Environment Variables

- API: copy `api/.env.example` to `api/.env`; `DATABASE_URL`, `CORS_ORIGINS`, `STORAGE_ROOT`, and `MAX_UPLOAD_BYTES` are supported.
- Web: `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000/api/v1`.

### Start Commands

```bash
docker compose up -d postgres
cd api && uv sync && uv run fastapi dev app/main.py
cd web && npm install && npm run dev
```

When Docker/PostgreSQL is unavailable, the repository also provides `./scripts/start-local.sh`. It initializes `data/local/scientific_rd.db` with the same Alembic migration and demo seed, then starts the API and Web together. This SQLite path is for local development only; the production/default configuration remains PostgreSQL.

### Migration Commands

```bash
cd api && uv run alembic upgrade head
```

### Seed Commands

```bash
cd api && uv run python -m app.seed
```

## 5. Actual Data Model

Tables: `projects`, `experiment_templates`, `experiments`, `attachments`, `experiment_revisions`.

Important constraints include unique project/experiment codes, active template selection, foreign keys, clone `parent_experiment_id`, attachment metadata separate from bytes, and unique `(experiment_id, revision_number)` revision numbering. `structured_data` and `note_document` are separate JSON columns. Revision rows are append-only through the API.

## 6. Actual API

- `GET /api/v1/health`
- `GET|POST /api/v1/projects`
- `GET|PATCH /api/v1/projects/{project_id}`
- `GET /api/v1/experiment-templates`
- `GET|POST /api/v1/projects/{project_id}/experiments`
- `GET|PATCH /api/v1/experiments/{experiment_id}`
- `POST /api/v1/experiments/{experiment_id}/clone`
- `GET|POST /api/v1/experiments/{experiment_id}/revisions`
- `GET /api/v1/experiments/{experiment_id}/revisions/{revision_id}`
- `GET|POST /api/v1/experiments/{experiment_id}/attachments`
- `GET|DELETE /api/v1/attachments/{attachment_id}` plus download route

## 7. Frontend Routes

- `/dashboard/overview`
- `/dashboard/projects`
- `/dashboard/projects/[projectId]`
- `/dashboard/projects/[projectId]/experiments/new`
- `/dashboard/experiments`
- `/dashboard/experiments/[experimentId]`

## 8. Third-party Dependencies

- Kiranism dashboard starter snapshot: MIT; SHA `7705dfc0d13889e45c26a55ad5908da6a7a9a605`.
- `@jsonforms/core`, `@jsonforms/react`, `@jsonforms/vanilla-renderers` 3.8.0: MIT.
- `@blocknote/core`, `@blocknote/react`, `@blocknote/shadcn` 0.54.0: MPL-2.0; no XL packages used.
- FastAPI, SQLAlchemy, Alembic, Pydantic, psycopg, jsonschema are installed through `api/pyproject.toml`/`uv.lock`.

## 9. Verification Results

- frontend lint: PASS (oxlint; inherited starter warnings remain).
- frontend typecheck: PASS.
- frontend tests: PASS — 2 tests.
- frontend build: PASS — Next.js 16.2.12.
- backend tests: PASS — 5 tests, including the API-level Phase 1 demo flow.
- migration blank DB: PENDING — Docker and PostgreSQL binaries unavailable (`docker: command not found`).
- seed idempotency: PASS against a temporary SQLite schema; production PostgreSQL seed pending.
- browser smoke: PASS for clean localhost loads of overview, projects, and experiments; meaningful content, no Next error overlay, no console errors. API-offline state was intentionally observed.
- demo scenario: PARTIAL — UI route path and API behavior are implemented; full live-API scenario awaits PostgreSQL.

## 10. Known Issues

### Blocker

- None in source code. PostgreSQL-backed verification is environment-blocked until Docker/PostgreSQL is available.

### Non-blocking debt

- npm audit reported three dependency advisories from the starter dependency graph; no forced upgrade was applied.
- A few inherited starter components still emit oxlint warnings.
- The workspace currently uses local filesystem attachments, not object storage.

### Intentionally deferred

Measurement, CSV/XLSX import, charts, Compare/batch workflows, Zotero/literature, embeddings/pgvector, AI, LangGraph, Langfuse, MCP, permissions/collaboration, S3/MinIO, jobs, notifications, and instrument integrations remain outside Phase 1.

## 11. Architectural Decisions Made During Implementation

- npm is the frontend package runner because Bun is not installed.
- Google-hosted `next/font` imports were removed so builds work offline; the theme’s Geist/system CSS fallback remains.
- The starter’s product/user routes and mock API routes were removed from the active build surface.
- JSON Forms uses its official vanilla renderer set with a small wrapper style layer rather than a new renderer library.

## 12. Phase 2 Constraints

Keep the API client boundary and the five Phase 1 tables stable. Preserve separate `structured_data` and `note_document` storage, append-only revisions, clone lineage, and the `StorageAdapter` abstraction. Do not add Phase 2/3 features to the Phase 1 navigation or migration without an updated execution plan.

## 13. Recommended Next Action

Run the Compose/API startup path on a Docker-enabled machine, execute `docs/DEMO_SCENARIO.md` end-to-end, and update this handoff from PARTIAL to PASS only after the blank-DB migration and live persistence checks succeed.
