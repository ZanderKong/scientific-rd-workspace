# Phase 1 — Foundation + ELN Core

## 1. Status

- **PASS** — all Phase 1 P0 acceptance criteria passed against PostgreSQL 17.11.
- Closeout implementation commit: `ba86520`; this document is finalized by its containing commit.
- Audit date: 2026-09-01.
- Phase 2/3 functionality was not started.

## 2. Delivered Product Slice

The repository contains a persistent Next.js 16/React 19 web workspace and a FastAPI/SQLAlchemy API for:

`Project → Experiment → Structured Properties → Rich Note → Attachments → Clone → Revisions`

Structured experiment properties are rendered by JSON Forms and validated again by the API against the exact server-owned template version bound to the experiment. Rich notes are stored separately as BlockNote JSON. Attachment bytes use the local storage adapter while authoritative metadata stays in PostgreSQL. Clones receive new identities and parent lineage. Revisions are append-only snapshots.

## 3. Phase 1 Closeout Fixes

1. The revision viewer now reads `snapshot_json.experiment.note_document`. It renders snapshot metadata, schema-driven structured properties, BlockNote content, and attachment metadata in read-only form; raw JSON remains an optional diagnostic disclosure.
2. `ExperimentTemplate` now uses immutable version rows with unique `(key, version)`. Migration `0002_immutable_template_versions` replaces the former unique-key constraint. Historical experiments retain their exact `template_id` and `template_version`; schema-bearing fields cannot be updated in place, while `is_active` remains a lifecycle toggle.
3. Attachment deletion commits metadata removal before deleting bytes. A failed database commit therefore cannot leave authoritative metadata pointing to deleted bytes. A later byte-cleanup failure is logged and returned as a diagnostic 500, leaving only a non-authoritative orphan for server cleanup.
4. `.github/workflows/phase-1-ci.yml` adds PostgreSQL 17 CI. It checks a blank-database Alembic upgrade, migration/model parity, seed idempotency, all backend tests against PostgreSQL, and frontend lint, typecheck, tests, and production build.
5. This handoff now matches the implementation, including the revision detail parameter `{revision_number}`.

## 4. Repository Structure

- `web/` — Next.js application shell, Phase 1 routes, JSON Forms, BlockNote, typed API client, and Vitest tests.
- `api/` — FastAPI application, SQLAlchemy models, Alembic migrations, seed, storage adapter, and pytest suite.
- `.github/workflows/phase-1-ci.yml` — PostgreSQL 17 backend and frontend CI jobs.
- `docker-compose.yml` — PostgreSQL 17 development service.
- `data/uploads/` — ignored local attachment storage root.
- `third_party_licenses/` and `THIRD_PARTY_NOTICES.md` — reuse attribution.

## 5. Runtime

### Standard PostgreSQL path

Prerequisites: Node.js 22+, npm, Python 3.11+, uv, and Docker Desktop.

```bash
cp api/.env.example api/.env
docker compose up -d postgres

cd api
uv sync --locked
uv run alembic upgrade head
uv run python -m app.seed
uv run fastapi dev app/main.py
```

In another terminal:

```bash
cd web
npm ci
npm run dev
```

Open `http://localhost:3000/dashboard/overview`.

API configuration supports `DATABASE_URL`, `CORS_ORIGINS`, `STORAGE_ROOT`, and `MAX_UPLOAD_BYTES`. The web client uses `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8000/api/v1`.

### Docker-free development fallback

`./scripts/start-local.sh` migrates and seeds `data/local/scientific_rd.db`, then starts API and Web together. This SQLite path is for local development convenience only; PostgreSQL remains authoritative for Phase 1 acceptance and the default shared runtime.

## 6. Data Model

Tables: `projects`, `experiment_templates`, `experiments`, `attachments`, and `experiment_revisions`.

Important guarantees:

- unique project and experiment codes;
- unique immutable template versions by `(key, version)`;
- permanent experiment binding to an exact template row/version;
- server-side structured-data validation against that bound schema;
- clone lineage through `parent_experiment_id`;
- separate `structured_data` and `note_document` JSONB columns;
- attachment metadata separate from bytes;
- unique `(experiment_id, revision_number)` and append-only revisions through the API.

## 7. API Surface

- `GET /api/v1/health`
- `GET|POST /api/v1/projects`
- `GET|PATCH /api/v1/projects/{project_id}`
- `GET /api/v1/experiment-templates`
- `GET /api/v1/experiment-templates/{template_id}`
- `GET /api/v1/experiments`
- `GET|POST /api/v1/projects/{project_id}/experiments`
- `GET|PATCH /api/v1/experiments/{experiment_id}`
- `POST /api/v1/experiments/{experiment_id}/clone`
- `GET|POST /api/v1/experiments/{experiment_id}/revisions`
- `GET /api/v1/experiments/{experiment_id}/revisions/{revision_number}`
- `GET|POST /api/v1/experiments/{experiment_id}/attachments`
- `GET /api/v1/attachments/{attachment_id}/download`
- `DELETE /api/v1/attachments/{attachment_id}`

## 8. Frontend Routes

- `/dashboard/overview`
- `/dashboard/projects`
- `/dashboard/projects/[projectId]`
- `/dashboard/projects/[projectId]/experiments/new`
- `/dashboard/experiments`
- `/dashboard/experiments/[experimentId]`

## 9. Final P0 Audit

The closeout used a real UTF-8 PostgreSQL 17.11 server on macOS because Docker was unavailable. The same database checks are encoded in GitHub Actions with the `postgres:17-alpine` service image.

| P0 acceptance criterion | Result and evidence |
| --- | --- |
| PostgreSQL, API, and Web start | PASS — PostgreSQL 17.11, FastAPI, and Next.js were run together. |
| Health and CORS | PASS — live `/api/v1/health` returned `{"status":"healthy"}` and browser requests succeeded. |
| Blank database migration | PASS — `alembic upgrade head` applied `0001` and `0002` on blank PostgreSQL. |
| Migration/model parity | PASS — `alembic check` reported no new upgrade operations. |
| Seed idempotency | PASS — seed ran twice; one PRJ-001, one template v1, and three demo experiments remained. |
| Project and experiment CRUD | PASS — PostgreSQL-backed API tests and browser flow passed. |
| Schema validation | PASS — valid writes pass and invalid/unknown structured fields return explanatory 4xx responses. |
| Exact template-version binding | PASS — tests cover old inactive version use, same-key v2 creation, duplicate rejection, and immutable schema rows. |
| Structured-property editing | PASS — EXP-046 starch was changed from `1` to `0.5`, saved, refreshed, and retained. |
| Rich-note storage | PASS — note JSON remains separate and is covered by the PostgreSQL demo test. |
| Attachment lifecycle | PASS — upload, SHA-256-verified download, delete, and post-delete 404 succeeded against the live PostgreSQL API. Failure-ordering tests cover database-commit and byte-cleanup faults. |
| Revision creation/viewing | PASS — revision created on PostgreSQL; viewer displayed nested note and disabled structured controls. |
| Clone and lineage | PASS — browser-created EXP-046 retained template v1, new identity, draft state, and parent lineage. |
| Refresh and service restart persistence | PASS — clone title and starch `0.5` remained after PostgreSQL, API, and Web restart. |
| Backend quality | PASS — Ruff check/format and 11 pytest tests; pytest ran with asserted PostgreSQL dialect. |
| Frontend quality | PASS — lint, typecheck, 4 Vitest tests, format check, and Next.js 16.2.12 production build. |
| License and repository hygiene | PASS — attribution retained, no nested `.git`, planning documents preserved. |

Browser inspection also confirmed there was no Next.js error overlay and no JSON Forms renderer error. The only observed browser diagnostic was the non-blocking development `metadataBase` warning.

## 10. Third-party Dependencies

- Kiranism dashboard starter snapshot: MIT; SHA `7705dfc0d13889e45c26a55ad5908da6a7a9a605`.
- `@jsonforms/core`, `@jsonforms/react`, `@jsonforms/vanilla-renderers` 3.8.0: MIT.
- `@blocknote/core`, `@blocknote/react`, `@blocknote/shadcn` 0.54.0: MPL-2.0; no XL packages are used.
- FastAPI, SQLAlchemy, Alembic, Pydantic, psycopg, and jsonschema are locked in `api/uv.lock`.

## 11. Non-blocking Debt and Deferred Scope

- The inherited starter dependency graph reports npm audit advisories and several oxlint warnings; neither blocks the Phase 1 path.
- Starlette emits one upstream TestClient/httpx deprecation warning in pytest.
- Phase 1 intentionally uses local filesystem attachment bytes, not object storage.
- Measurement, Compare, CSV/XLSX import, charts, Literature/Zotero, embeddings/pgvector, AI, LangGraph, Langfuse, MCP, permissions/collaboration, jobs, notifications, and instrument integrations remain deferred. No Phase 2/3 tables, routes, navigation, or runtime dependencies were added.

## 12. Closeout Decision

Phase 1 is frozen as passing. Any Phase 2 work requires a separate reviewed execution plan and explicit authorization.
