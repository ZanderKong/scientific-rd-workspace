# Phase 2 — Scientific Workflow Handoff

## 1. Status

- **PASS** — all Phase 2 P0 acceptance criteria passed, including the authoritative PostgreSQL 17 GitHub Actions gates.
- **Verdict:** `PHASE 2 PASS`.
- **Phase 1 baseline:** `9bb494d` (Phase 1 remains frozen and passing).
- **Implementation commit:** `b916292` (`Implement Phase 2 scientific workflow`).
- **Accepted source commit:** `939bf82` (`Document Phase 2 handoff commit`).
- **Closeout date:** 2026-09-01.
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
| Backend tests | PASS | 18 tests locally and the complete suite against PostgreSQL 17 in GitHub Actions |
| Blank Alembic migration | PASS | `alembic upgrade head` through `0004` on a blank PostgreSQL 17 database |
| Alembic parity | PASS | `alembic check` reported no model/migration differences against PostgreSQL 17 |
| Seed idempotency | PASS | seed ran twice against PostgreSQL 17; expected Phase 2 entity counts remained stable |
| Frontend lint | PASS | `cd web && npm run lint` (only inherited starter warnings) |
| Frontend format | PASS | `cd web && npm run format:check` |
| Frontend typecheck | PASS | `cd web && npm run typecheck` |
| Frontend tests | PASS | `cd web && npm run test` — 6 tests |
| Production build | PASS | `cd web && npm run build` |
| Local runtime smoke | PASS | API health/projects and web Compare route returned successfully |
| PostgreSQL 17 acceptance | PASS | Phase 2 workflow run `33522448986`, Backend / PostgreSQL 17 job `99904822938` |

SQLite remains a development fallback only. Final Phase 2 acceptance is backed by the successful PostgreSQL 17 GitHub Actions run below.

## 6. GitHub Actions acceptance

The successful Phase 2 acceptance run is [Phase 2 Scientific Workflow CI #33522448986](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33522448986):

- commit: `939bf82dc44aa2a8b97634827165fbe942803a47`;
- branch/event: `main`, `push`;
- result: `completed / success`;
- started: 2026-09-01 14:54:51 UTC;
- completed: 2026-09-01 14:56:09 UTC;
- `Backend / PostgreSQL 17`: success — container initialization, locked dependency install, blank-database migration, migration/model parity, backend lint/format, idempotent Phase 2 seed, and backend tests against PostgreSQL all passed;
- `Frontend`: success — locked dependency install, lint, format check, typecheck, tests, and production build all passed.

The same accepted commit also passed [Phase 1 CI #33522448939](https://github.com/ZanderKong/scientific-rd-workspace-codex-pack-v0.1/actions/runs/33522448939), including its PostgreSQL 17 backend and frontend regression jobs. This confirms that the Phase 1 guarantees remained green at Phase 2 closeout.

## 7. Deliberately deferred

- Zotero synchronization remains optional behind `LiteratureProvider`; manual Literature is the Phase 2 P0 path.
- Universal scientific file parsing, arbitrary schemas, unit conversion, interpolation/resampling, and instrument-specific adapters are out of scope.
- AI, RAG, embeddings, pgvector, LangGraph, Langfuse, MCP, automated findings, and Evidence Gate decisions remain Phase 3.

## 8. Handoff decision

`PHASE 2 PASS`. Phase 2 is formally closed at accepted source commit `939bf82`. Phase 1 guarantees remain unchanged, and Phase 3 has not begun.
